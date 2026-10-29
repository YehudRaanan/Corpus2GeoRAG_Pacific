"""Source eligibility is positional, conservative and independent of matching."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot import filter_source_content as scope
from GG_Data.entity_resolution.luke_pilot.data import sha256


def classify(raw, text, occurrence=0):
    start = [i for i in range(len(raw)) if raw.startswith(text, i)][occurrence]
    spans, headings = scope.source_intervals(raw)
    return scope.classify_span(start, start + len(text), spans, headings)


@pytest.mark.parametrize(
    "raw,text,status",
    [
        ("Japan is a country.", "Japan", "KEEP"),
        ("{{Infobox unit|dates=1942{{sfn|Smith|1996}}}}", "1942", "KEEP"),
        ("{{Infobox unit|dates=1942{{sfn|Smith|1996}}}}", "1996", "EXCLUDE"),
        (
            "{{blockquote|Japan<ref>{{cite book|publisher=Japan Press}}</ref>}}",
            "Press",
            "EXCLUDE",
        ),
        ("{{blockquote|Japan fought here.}}", "Japan", "KEEP"),
        ("[[File:Japan.jpg|thumb|A port in [[Japan]]]]", "Japan.jpg", "EXCLUDE"),
        ("[[File:Japan.jpg|thumb|A port in [[Japan]]]]", "port", "KEEP"),
        ("[[Category:Japan|AAA]]", "AAA", "EXCLUDE"),
        ("[[:Category:Kings of Chūzan|Kings of Chūzan]]", "Kings of Chūzan", "EXCLUDE"),
        ("The {{ship|Japanese battleship|Nagato|up=yes}} sailed.", "Nagato", "KEEP"),
        ("The {{ship|Japanese battleship|Nagato|up=yes}} sailed.", "yes", "EXCLUDE"),
        ("{{Infobox unit|country={{USA}}}}", "USA", "REVIEW"),
        (
            "{{Infobox unit|country={{flag|United States|1912}}}}",
            "United States",
            "KEEP",
        ),
        ("{{Infobox unit|country={{flag|United States|1912}}}}", "1912", "EXCLUDE"),
        ("{{Infobox unit|country={{unknown|Japan}}}}", "Japan", "REVIEW"),
        (
            "{{Infobox ship|displacement=4000{{Clarify|date=October 2011}}}}",
            "October 2011",
            "EXCLUDE",
        ),
        (
            "{{Infobox unit|country={{flagicon image|Flag_of_Japan.svg}}}}",
            "Japan",
            "EXCLUDE",
        ),
        ("Japan<ref name=x/> sailed to France.", "France", "KEEP"),
        ("Japan<ref group=note>France was also involved.</ref>", "France", "REVIEW"),
        ("<!-- Japan -->", "Japan", "EXCLUDE"),
        ("{{DEFAULTSORT:Japan}}", "Japan", "EXCLUDE"),
        ("[https://example.org/Japan Japan]", "example.org", "EXCLUDE"),
        (
            "== Bibliography ==\nJohn, History of Japan.\n== History ==\nJapan fought.",
            "John",
            "EXCLUDE",
        ),
        ("{|\n! Year !! Country\n|-\n|1944||Japan\n|}", "1944", "KEEP"),
        ("<gallery>\nJapan.jpg|Japan harbour\n</gallery>", "harbour", "KEEP"),
        ("<nowiki>{{ship|Japan}}</nowiki>", "Japan", "REVIEW"),
    ],
)
def test_source_rules(raw, text, status):
    assert classify(raw, text)["status"] == status


def test_visible_escaped_category_label_and_nested_citation_priority():
    raw = "[[:Category:Kings of Chūzan|Kings of Chūzan]]"
    assert classify(raw, "Chūzan", occurrence=1)["status"] == "KEEP"
    raw = "{{blockquote|Japan<ref>{{cite book|title=Japan}}</ref>}}"
    assert classify(raw, "Japan", occurrence=0)["status"] == "KEEP"
    assert classify(raw, "Japan", occurrence=1)["reason"] == "citation"


def test_partial_hidden_target_overlap_does_not_become_prose():
    assert classify("[[Japan|Japan]]", "Japan|Japan")["status"] == "REVIEW"


def fixture(tmp_path):
    raw = "Japan is here. <ref>{{cite book|publisher=Japan Press}}</ref> {{mystery|Japan}}"
    raw_path = tmp_path / "raw.txt"
    raw_path.write_bytes(raw.encode())
    # The revision collector binds the raw text to its saved API response.
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "ok": True,
                "response_text": json.dumps(
                    {
                        "parse": {
                            "pageid": 1,
                            "revid": 11,
                            "title": "Japan",
                            "wikitext": raw,
                        }
                    }
                ),
            }
        )
    )
    revisions = tmp_path / "revisions.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                dict(
                    page_id=1,
                    revision_id=11,
                    wikitext_path=str(raw_path),
                    sha256=sha256(raw_path),
                    evidence_path=str(evidence),
                )
            ]
        ),
        revisions,
    )
    starts = [0, raw.index("Japan Press"), raw.rindex("Japan")]
    rows = [
        dict(
            source_row_index=i,
            page_id=1,
            revision_id=11,
            passage_id="p",
            Text=raw,
            word="Japan",
            word_original="Japan",
            start=start,
            end=start + 5,
            entity_group="LOC",
            matched_qids=["Q17"],
        )
        for i, start in enumerate(starts)
    ]
    # Repair changes the matching name, never the original positional evidence.
    rows[1]["word"] = "Japan Press"
    return rows, revisions


def test_filter_preserves_all_original_columns_and_masks_context(tmp_path):
    rows, revisions = fixture(tmp_path)
    mentions = tmp_path / "mentions.parquet"
    original = pa.Table.from_pylist(rows)
    pq.write_table(original, mentions)
    summary = scope.filter_mentions(mentions, revisions, tmp_path / "output")
    result = pq.read_table(tmp_path / "output/mentions.parquet")
    assert result.select(original.column_names).equals(original)
    assert result["source_scope_status"].to_pylist() == ["KEEP", "EXCLUDE", "REVIEW"]
    assert "Japan Press" not in result["source_scope_context"][0].as_py()
    assert "mystery" not in result["source_scope_context"][0].as_py()
    assert summary["rows"] == 3
    assert summary["original_columns_preserved"] is True
    with pytest.raises(FileExistsError):
        scope.filter_mentions(mentions, revisions, tmp_path / "output")


def test_ambiguous_passage_and_invalid_offsets_stay_review(tmp_path):
    rows, revisions = fixture(tmp_path)
    rows[0].update(Text="Japan", start=0, end=5)
    rows[1]["start"] = -1
    mentions = tmp_path / "mentions.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    scope.filter_mentions(mentions, revisions, tmp_path / "output")
    result = pq.read_table(tmp_path / "output/mentions.parquet").to_pylist()
    assert result[0]["source_scope_reason"] == "nonunique_or_nonexact_raw_placement"
    assert result[1]["source_scope_reason"] == "invalid_original_offsets"


def test_mismatched_revision_hash_is_rejected(tmp_path):
    rows, revisions = fixture(tmp_path)
    revision_rows = pq.read_table(revisions).to_pylist()
    revision_rows[0]["sha256"] = "0" * 64
    pq.write_table(pa.Table.from_pylist(revision_rows), revisions)
    mentions = tmp_path / "mentions.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    with pytest.raises(ValueError, match="hash mismatch"):
        scope.filter_mentions(mentions, revisions, tmp_path / "output")


def test_country_display_override_and_explanatory_template():
    raw = "{{Infobox battle|combatant={{flag|Empire of Japan|name=Japan}}}}"
    assert classify(raw, "Empire of Japan")["status"] == "EXCLUDE"
    assert classify(raw, "Japan", occurrence=1)["status"] == "KEEP"
    raw = "{{Infobox unit|caption={{efn|Naha{{cite book|title=Tokyo}}}}}}"
    assert classify(raw, "Naha")["status"] == "REVIEW"
    assert classify(raw, "Tokyo")["status"] == "EXCLUDE"


@pytest.mark.parametrize(
    "raw,text",
    [
        ("<ref>{{cite book|title=Japan", "Japan"),
        ("[[File:Japan.jpg|thumb|Japan", "Japan.jpg"),
        ("{{unknown|Japan", "Japan"),
        ("{{ship|Japanese battleship|Nagato}} sailed", "Japanese battleship|Nagato"),
        ("{{ship|Japanese battleship|Nagato}} sailed", "Nagato}} sailed"),
    ],
)
def test_unparsed_or_cross_boundary_markup_stays_review(raw, text):
    assert classify(raw, text)["status"] == "REVIEW"


def test_multiline_media_option_is_not_a_caption():
    assert (
        classify("[[File:X.jpg|thumb|alt=Tokyo\nJapan]]", "Tokyo")["status"]
        == "EXCLUDE"
    )


def test_duplicate_helper_parameters_stay_review():
    assert (
        classify("{{flag|Japan|name=Tokyo|name=Osaka}}", "Tokyo")["status"] == "REVIEW"
    )


@pytest.mark.parametrize(
    "raw,text,status",
    [
        ("{{Ship|Japanese submarine|I-25||2}}", "Japanese", "EXCLUDE"),
        ("{{Ship|Japanese submarine|I-25||2}}", "I-25", "KEEP"),
        ("{{ship|Japanese battleship|Nagato||99}}", "Nagato", "REVIEW"),
        ("[[File:X.jpg|thumb=Tokyo]]", "Tokyo", "EXCLUDE"),
        ("[[File:X.jpg|100px|Japan harbour]]", "Japan", "REVIEW"),
        ("{{Infobox unit|image_flag=Flag of Japan.svg}}", "Japan", "EXCLUDE"),
        ("{{Infobox ship|Ship image=USS Japan.jpg}}", "Japan", "EXCLUDE"),
        ("<span class=Japan>France</span>", "Japan", "EXCLUDE"),
        ("<span class=Japan>France</span>", "France", "KEEP"),
    ],
)
def test_display_controls_and_hidden_image_fields(raw, text, status):
    assert classify(raw, text)["status"] == status


def test_empty_input_has_clear_error(tmp_path):
    mentions = tmp_path / "empty.parquet"
    pq.write_table(
        pa.table({"source_row_index": pa.array([], type=pa.int64())}), mentions
    )
    with pytest.raises(ValueError, match="non-empty"):
        scope.filter_mentions(
            mentions, tmp_path / "unused.parquet", tmp_path / "output"
        )


@pytest.mark.parametrize(
    "raw,text,status",
    [
        ("<ref>Hallis (2007), p. 15</ref>", "Hallis", "EXCLUDE"),
        ("<ref>Frank & Shaw (1968), pp. 489–490.</ref>", "Frank", "EXCLUDE"),
        ("<ref>The 15th Marines was an artillery regiment.</ref>", "Marines", "REVIEW"),
        (
            "<ref>They rejoined in China, see Frank & Shaw (1968), p. 490</ref>",
            "China",
            "REVIEW",
        ),
        ("<ref>Hallis (2007), p. 15, describes Japan.</ref>", "Japan", "REVIEW"),
        (
            "{{Quote box|quote=Japan fought here.{{sfn|Smith|2000}}|width=30%}}",
            "Japan",
            "KEEP",
        ),
        ("{{Quote box|quote=Japan{{sfn|Smith|2000}}|width=30%}}", "Smith", "EXCLUDE"),
        (
            "{{Quote box|quote=Japan|title=Unknown source|width=30%}}",
            "Unknown",
            "REVIEW",
        ),
        ("{{Quote box|quote=Japan|align=right}}", "right", "EXCLUDE"),
        ("{{plainlist|* Japan\n* France|class=Japan}}", "France", "KEEP"),
        ("{{plainlist|* France|class=Japan}}", "Japan", "EXCLUDE"),
        ("{{ubl|{{flag|United States|1912}}|Japan}}", "United States", "KEEP"),
        ("{{ubl|{{flag|United States|1912}}|Japan}}", "1912", "EXCLUDE"),
        ("{{bulleted list|{{unknown|Japan}}|France}}", "Japan", "REVIEW"),
        (
            "{{hlist|[[Indian Ocean]]|[[Pacific Ocean]]}}",
            "Indian Ocean]]|[[Pacific",
            "REVIEW",
        ),
        ("[[File:X.jpg|thumb|Japan harbour|left|alt=Tokyo]]", "Japan", "KEEP"),
        ("[[File:X.jpg|Japan harbour|thumb]]", "Japan", "KEEP"),
        ("[[File:X.jpg|thumb|Japan harbour|left|alt=Tokyo]]", "Tokyo", "EXCLUDE"),
        ("[[File:X.jpg|Japan harbour|alt=Tokyo]]", "Japan", "REVIEW"),
        (
            "{{multiple image|image1=Japan.jpg|caption1=Tokyo|footer=Osaka|width=200}}",
            "Tokyo",
            "KEEP",
        ),
        (
            "{{multiple image|image1=Japan.jpg|caption1=Tokyo|footer=Osaka}}",
            "Japan",
            "EXCLUDE",
        ),
        (
            "{{multiple image|image1=X.jpg|caption1=Tokyo{{sfn|Japan|2000}}}}",
            "Japan",
            "EXCLUDE",
        ),
        ("{{main|Japan}}", "Japan", "EXCLUDE"),
        (
            "{{ribbon devices|ribbon=Medal of Honor ribbon.svg|alt=Japan}}",
            "Japan",
            "EXCLUDE",
        ),
        ("{{font color|red|Japan}}", "Japan", "KEEP"),
        ("{{font color|red|Japan}}", "red", "EXCLUDE"),
    ],
)
def test_second_pass_source_rules(raw, text, status):
    assert classify(raw, text)["status"] == status


def test_read_old_policy_and_reject_mixed_versions():
    row = dict(
        source_scope_policy_version="article-source-v1",
        source_scope_status="KEEP",
        source_scope_context="Japan",
    )
    assert scope.source_policy([row]) == "article-source-v1"
    new = dict(row, source_scope_policy_version="article-source-v2")
    assert scope.source_policy([new]) == "article-source-v2"
    with pytest.raises(ValueError, match="mixed"):
        scope.source_policy([row, new])


@pytest.mark.parametrize(
    "raw,text,status",
    [
        ("<ref>Stockman, p. 18</ref>", "Stockman", "EXCLUDE"),
        ("<ref>Schmidt 1982, page 36.</ref>", "Schmidt", "EXCLUDE"),
        ("<ref>Frank & Shaw (1968), pp. 49–50, 53, 55.</ref>", "Frank", "EXCLUDE"),
        (
            "{{London Gazette|issue=35558|date=12 May 1942||page=2111|supp=y}}",
            "May",
            "EXCLUDE",
        ),
        ("{{London Gazette|date=1942|quote=Japan was involved}}", "Japan", "REVIEW"),
        (
            "{{csr|register=MSI|id=6114753|shipname=Barber|access-date=2009}}",
            "Barber",
            "EXCLUDE",
        ),
        (
            "{{Gallery|File:Japan.jpg|Japan harbour|File:Tokyo.jpg|Tokyo}}",
            "harbour",
            "KEEP",
        ),
        ("{{Gallery|File:Japan.jpg|Japan harbour}}", "Japan.jpg", "EXCLUDE"),
        ("{{Gallery|File:Japan.jpg|Japan{{sfn|Tokyo|2000}}}}", "Tokyo", "EXCLUDE"),
        ("{{Gallery|Japan harbour|File:Tokyo.jpg|Tokyo}}", "harbour", "REVIEW"),
        (
            "<gallery>File:X.jpg|Rome, Georgia.\nFile:Y.jpg|Japan</gallery>",
            "Rome",
            "KEEP",
        ),
        ("<gallery>File:Japan.jpg|Tokyo</gallery>", "Japan.jpg", "EXCLUDE"),
        ("<gallery>File:Japan.jpg|Tokyo</gallery>", "JPG|Tokyo", "REVIEW"),
        (
            "<gallery>File:X.jpg|{{ship|Japanese submarine|I-25||2}}</gallery>",
            "I-25",
            "KEEP",
        ),
        (
            "<gallery>File:X.jpg|{{ship|Japanese submarine|I-25||2}}</gallery>",
            "Japanese",
            "EXCLUDE",
        ),
        ("<gallery>File:X.jpg|{{unknown|Japan}}</gallery>", "Japan", "REVIEW"),
    ],
)
def test_gallery_and_short_citation_boundaries(raw, text, status):
    # A boundary example is deliberately case-sensitive, like the original offsets.
    raw = (
        raw.replace("Japan.jpg|Tokyo", "Japan.JPG|Tokyo")
        if text == "JPG|Tokyo"
        else raw
    )
    assert classify(raw, text)["status"] == status


def test_gallery_nested_link_and_citation_context():
    raw = "<gallery>File:X.jpg|[[Tokyo|Japan]] {{cite book|publisher=Kyoto}}</gallery>"
    assert classify(raw, "Tokyo")["status"] == "EXCLUDE"
    assert classify(raw, "Japan")["status"] == "KEEP"
    assert classify(raw, "Kyoto")["status"] == "EXCLUDE"
    spans, headings = scope.source_intervals(raw)
    context = scope.masked_source(raw, spans, headings)
    assert "Japan" in context
    assert "Tokyo" not in context and "Kyoto" not in context
    assert "File:X.jpg" not in context


def test_displayed_quote_does_not_unmask_citation_context():
    raw = "{{quote box|quote=Japan{{sfn|Smith|2000}}|width=30%}}"
    spans, headings = scope.source_intervals(raw)
    context = scope.masked_source(raw, spans, headings)
    assert "Japan" in context
    assert "Smith" not in context and "30%" not in context


@pytest.mark.parametrize(
    "raw,text,status",
    [
        ("<gallery>File:X.jpg|alt=Tokyo</gallery>", "Tokyo", "EXCLUDE"),
        ("<gallery>File:X.jpg|link=Tokyo</gallery>", "Tokyo", "EXCLUDE"),
        ("{{plainlist|Japan|Tokyo}}", "Tokyo", "REVIEW"),
        ("{{plain list|Japan|Tokyo}}", "Japan", "KEEP"),
        ("{{hlist|Japan|Tokyo}}", "Tokyo", "KEEP"),
        ("<ref>Japan and China pages 12</ref>", "Japan", "REVIEW"),
    ],
)
def test_final_review_hidden_gallery_options_and_list_shape(raw, text, status):
    assert classify(raw, text)["status"] == status
    spans, headings = scope.source_intervals(raw)
    context = scope.masked_source(raw, spans, headings)
    if status != "KEEP":
        assert text not in context

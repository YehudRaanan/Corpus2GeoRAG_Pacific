"""Source name repair must preserve original rows and avoid ambiguous placement."""

import hashlib
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def run_prepare(tmp_path, raw, mentions, entities=(), evidence=()):
    from GG_Data.entity_resolution.hundred_page_pilot.prepare_mentions import prepare

    raw_path = tmp_path / "raw.txt"
    raw_path.write_text(raw, encoding="utf-8", newline="")
    binding = tmp_path / "binding.json"
    binding.write_text(
        json.dumps(
            {
                "ok": True,
                "response_text": json.dumps(
                    {
                        "parse": {
                            "pageid": 1,
                            "revid": 2,
                            "title": "Page",
                            "wikitext": raw,
                        }
                    }
                ),
            }
        ),
        encoding="utf-8",
    )
    revisions = [
        {
            "page_id": 1,
            "revision_id": 2,
            "wikitext_path": str(raw_path),
            "evidence_path": str(binding),
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
        }
    ]
    rows = []
    for i, mention in enumerate(mentions):
        text = mention.get("Text", raw)
        word = mention["word"]
        start = mention.get("start", text.index(word))
        rows.append(
            {
                "page_id": 1,
                "revision_id": 2,
                "source_row_index": i,
                "passage_id": str(i) if mention.get("Text") else "whole",
                "entity_group": "PER",
                "Text": text,
                "start": start,
                "end": start + len(word),
                **mention,
            }
        )
    paths = {}
    for key, data in (
        ("mentions", rows),
        ("revisions", revisions),
        ("entities", list(entities)),
        ("evidence", list(evidence)),
    ):
        paths[key] = tmp_path / f"{key}.parquet"
        pq.write_table(pa.Table.from_pylist(data), paths[key])
    summary = prepare(
        paths["mentions"],
        paths["revisions"],
        paths["entities"],
        paths["evidence"],
        tmp_path / "out",
    )
    output = pq.read_table(tmp_path / "out/mentions.parquet").to_pylist()
    spans = pq.read_table(tmp_path / "out/recovered_spans.parquet").to_pylist()
    bridge = pq.read_table(tmp_path / "out/mention_span_bridge.parquet").to_pylist()
    return rows, output, spans, bridge, summary


def ent(label, qid="Q1", aliases=()):
    return {
        "page_id": 1,
        "revision_id": 2,
        "qid": qid,
        "label": label,
        "aliases": list(aliases),
    }


def test_full_literal_name_can_support_several_original_rows(tmp_path):
    rows, output, spans, bridge, summary = run_prepare(
        tmp_path,
        "John Smith met Mary Jones.",
        [{"word": "Jo"}, {"word": "Smi"}, {"word": "Ma"}],
        [ent("John Smith"), ent("Mary Jones", "Q2")],
    )
    assert [r["word"] for r in output] == ["John Smith", "John Smith", "Mary Jones"]
    assert all(
        r["repair_status"] == "repaired" and r["repair_qid_guided"] for r in output
    )
    assert [r["source_candidate_qids"] for r in output] == [["Q1"], ["Q1"], ["Q2"]]
    for before, after in zip(rows, output):
        assert all(after[k] == v for k, v in before.items() if k != "word")
        assert after["word_original"] == before["word"]
        assert (
            after["Text"][after["repaired_start"] : after["repaired_end"]]
            == after["word"]
        )
    john_ids = {b["source_row_index"] for b in bridge if b["surface"] == "John Smith"}
    assert john_ids == {0, 1}
    assert summary["original_rows"] == 3


def test_date_is_preserved_and_has_no_candidate_evidence(tmp_path):
    _, rows, _, bridge, _ = run_prepare(
        tmp_path,
        "May 1942",
        [{"word": "1942", "entity_group": "DATE"}],
        [ent("May 1942")],
    )
    assert rows[0]["word"] == "1942"
    assert rows[0]["repair_status"] == "date_excluded"
    assert rows[0]["source_candidate_qids"] == []
    assert not bridge


@pytest.mark.parametrize(
    "labels",
    [
        ["World War II", "World War II Database"],
        ["Marine Corps", "Marine Corps Air Station"],
    ],
)
def test_competing_complete_source_surfaces_remain_ambiguous(tmp_path, labels):
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        labels[1],
        [{"word": labels[0]}],
        [ent(labels[0]), ent(labels[1], "Q2")],
    )
    assert rows[0]["word"] == labels[0]
    assert rows[0]["repair_status"] == "ambiguous_surface"
    assert rows[0]["repair_alternatives"] == sorted(labels)
    assert rows[0]["source_candidate_qids"] == ["Q1", "Q2"]


def test_repeated_passage_has_no_first_match_repair(tmp_path):
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        "John Smith. John Smith.",
        [{"word": "John", "Text": "John Smith."}],
        [ent("John Smith")],
    )
    assert rows[0]["word"] == "John"
    assert rows[0]["repair_status"] == "ambiguous_raw_placement"
    assert rows[0]["source_candidate_qids"] == []


def test_normalized_passage_is_flagged_without_guessed_offsets(tmp_path):
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        "John  Smith.",
        [{"word": "John", "Text": "John Smith."}],
        [ent("John Smith")],
    )
    assert rows[0]["word"] == "John"
    assert rows[0]["repair_status"] == "normalized_raw_placement_unrepaired"


def test_nihongo_and_split_citation_author_need_no_new_qid(tmp_path):
    raw = "{{nihongo|Shigeru Fukudome|福留 繁}} {{cite book|last=Smith|first=John|title=A Book}}"
    _, rows, _, bridge, _ = run_prepare(
        tmp_path, raw, [{"word": "Shigeru"}, {"word": "Smith"}, {"word": "John"}]
    )
    assert [r["word"] for r in rows] == ["Shigeru Fukudome", "John Smith", "John Smith"]
    assert all(
        not r["repair_qid_guided"] and r["source_candidate_qids"] == [] for r in rows
    )
    assert len(bridge) == 3


def test_nested_infobox_name_does_not_cover_unrelated_fields(tmp_path):
    raw = "{{Infobox person\n|name={{nowrap|John Smith}}\n|birth_place=Somewhere\n}}"
    _, rows, _, _, _ = run_prepare(
        tmp_path, raw, [{"word": "John"}, {"word": "Somewhere", "entity_group": "LOC"}]
    )
    assert rows[0]["word"] == "John Smith"
    assert rows[1]["word"] == "Somewhere"
    assert not rows[1]["source_candidate_qids"]


def test_recovered_only_names_do_not_create_original_rows(tmp_path):
    _, rows, spans, _, summary = run_prepare(
        tmp_path,
        "John Smith and Mary Jones",
        [{"word": "John"}],
        [ent("John Smith"), ent("Mary Jones", "Q2")],
    )
    assert len(rows) == 1
    assert any(
        r["surface"] == "Mary Jones" and not r["source_row_indices"] for r in spans
    )
    assert summary["recovered_only_spans"] == 1


def test_qid_candidates_are_same_page_revision_only(tmp_path):
    wrong = {**ent("John Smith"), "revision_id": 3}
    _, rows, _, _, _ = run_prepare(tmp_path, "John Smith", [{"word": "John"}], [wrong])
    assert rows[0]["word"] == "John"
    assert rows[0]["source_candidate_qids"] == []


def test_ordinary_link_support_uses_name_not_unrelated_template_fields(tmp_path):
    raw = "{{Infobox person|name=[[John Smith]]|birth_date=1942}}"
    start = raw.index("[[")
    evidence = [
        {
            "page_id": 1,
            "revision_id": 2,
            "raw_start": start,
            "raw_end": start + len("[[John Smith]]"),
            "raw_text": "[[John Smith]]",
            "target_title": "John Smith",
            "qid": "Q1",
            "link_origin": "RAW_DIRECT_LINK",
        }
    ]
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        raw,
        [{"word": "John"}, {"word": "1942", "entity_group": "MISC"}],
        [],
        evidence,
    )
    assert rows[0]["word"] == "John Smith" and rows[0]["source_candidate_qids"] == [
        "Q1"
    ]
    assert rows[1]["word"] == "1942" and rows[1]["source_candidate_qids"] == []


def test_short_source_name_cannot_shrink_a_complete_original_name(tmp_path):
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        "Marine Corps Air Station",
        [{"word": "Marine Corps Air Station"}],
        [ent("Marine Corps")],
    )
    assert rows[0]["word"] == "Marine Corps Air Station"
    assert rows[0]["repair_status"] == "partial_source_overlap"
    assert rows[0]["source_candidate_qids"] == ["Q1"]


def test_conflict_is_preserved_when_original_is_the_longer_name(tmp_path):
    labels = ["Marine Corps", "Marine Corps Air Station"]
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        labels[1],
        [{"word": labels[1]}],
        [ent(labels[0]), ent(labels[1], "Q2")],
    )
    assert rows[0]["word"] == labels[1]
    assert rows[0]["repair_status"] == "ambiguous_surface"
    assert rows[0]["repair_alternatives"] == sorted(labels)


def test_documented_ship_target_uses_full_name_but_only_name_parameter_overlap(
    tmp_path,
):
    raw = "{{Ship|USS|Johnston|DD-557|1}}"
    evidence = [
        {
            "page_id": 1,
            "revision_id": 2,
            "raw_start": 0,
            "raw_end": len(raw),
            "raw_text": raw,
            "target_title": "USS Johnston (DD-557)",
            "qid": "Q1",
            "link_origin": "RAW_SHIP_TEMPLATE",
        }
    ]
    _, rows, spans, _, _ = run_prepare(
        tmp_path,
        raw,
        [
            {"word": "Johnston", "entity_group": "MISC"},
            {"word": "DD-557", "entity_group": "MISC"},
        ],
        [],
        evidence,
    )
    assert rows[0]["word"] == "USS Johnston (DD-557)"
    assert rows[0]["repair_method"] == "documented_template_target"
    assert rows[0]["source_candidate_qids"] == ["Q1"]
    assert rows[1]["word"] == "DD-557" and not rows[1]["source_candidate_qids"]
    assert any(
        not r["surface_is_literal"] and r["raw_text"] == "Johnston" for r in spans
    )


def test_review_template_qid_cannot_trigger_automatic_name_repair(tmp_path):
    raw = "{{Ship|Japanese destroyer|Asagumo|1938}}"
    evidence = [
        {
            "page_id": 1,
            "revision_id": 2,
            "raw_start": 0,
            "raw_end": len(raw),
            "raw_text": raw,
            "target_title": "Japanese destroyer Asagumo (1938)",
            "qid": None,
            "qid_status": "IDENTIFIER_YEAR_CHANGED_REVIEW",
            "recovery_status": "REVIEW_OR_NO_QID",
            "link_origin": "RAW_SHIP_TEMPLATE",
        }
    ]
    _, rows, spans, _, _ = run_prepare(
        tmp_path, raw, [{"word": "Asagumo", "entity_group": "MISC"}], [], evidence
    )
    assert rows[0]["word"] == "Asagumo"
    assert rows[0]["repair_status"] == "source_target_review"
    assert any(r["surface"] == "Japanese destroyer Asagumo (1938)" for r in spans)


def test_source_comment_does_not_break_parser_offsets(tmp_path):
    raw = "{{Infobox person|name=John<!-- note --> Smith}}"
    _, rows, _, _, _ = run_prepare(tmp_path, raw, [{"word": "John"}])
    assert rows[0]["word"] == "John Smith"


def test_citation_author_with_wrong_daniel_type_stays_for_review(tmp_path):
    raw = "{{cite book|last=Smith|first=John|title=Book}}"
    _, rows, _, _, _ = run_prepare(
        tmp_path, raw, [{"word": "Smith", "entity_group": "ORG"}]
    )
    assert rows[0]["word"] == "Smith"
    assert rows[0]["repair_status"] == "source_type_review"


def test_invalid_target_evidence_is_rejected_before_outputs(tmp_path):
    raw = "[[John Smith]]"
    evidence = [
        {
            "page_id": 1,
            "revision_id": 2,
            "raw_start": 0,
            "raw_end": len(raw),
            "raw_text": "[[A different person]]",
            "target_title": "John Smith",
            "qid": "Q1",
            "link_origin": "RAW_DIRECT_LINK",
        }
    ]
    with pytest.raises(ValueError, match="raw text does not match"):
        run_prepare(tmp_path, raw, [{"word": "John"}], [], evidence)
    assert not (tmp_path / "out").exists()


def test_protected_names_do_not_produce_repair_evidence(tmp_path):
    raw = "<nowiki>{{nihongo|John Smith|Name}}</nowiki>"
    _, rows, spans, _, _ = run_prepare(
        tmp_path, raw, [{"word": "John"}], [ent("John Smith")]
    )
    assert rows[0]["word"] == "John"
    assert spans == []


def test_qid_label_inside_unlisted_longer_proper_name_stays_for_review(tmp_path):
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        "World War II Database",
        [{"word": "World War"}],
        [ent("World War II", "Q362")],
    )
    assert rows[0]["word"] == "World War"
    assert rows[0]["repair_status"] == "source_context_review"
    assert rows[0]["source_candidate_qids"] == ["Q362"]


def test_lexically_cut_qid_label_in_ordinary_prose_still_repairs_full_name(tmp_path):
    _, rows, _, _, _ = run_prepare(
        tmp_path,
        "ships served in World War II, then returned.",
        [{"word": "World Wa"}],
        [ent("World War II", "Q362")],
    )
    assert rows[0]["word"] == "World War II"
    assert rows[0]["repair_status"] == "repaired"


def test_hidden_wikilink_title_is_not_visible_infobox_name_support(tmp_path):
    raw = "{{Infobox person|name=[[John Smith|Smith]]}}"
    _, rows, _, _, _ = run_prepare(tmp_path, raw, [{"word": "John"}])
    assert rows[0]["word"] == "John"
    assert rows[0]["repair_status"] == "unchanged"


def test_comment_inside_name_is_not_support_for_comment_mentions(tmp_path):
    raw = "{{Infobox person|name=John<!-- note --> Smith}}"
    _, rows, _, _, _ = run_prepare(tmp_path, raw, [{"word": "note"}])
    assert rows[0]["word"] == "note"
    assert rows[0]["repair_status"] == "unchanged"


@pytest.mark.parametrize(
    "raw,word,label",
    [
        ("{{Main|Landing at Nadzab}}", "Nadzab", "Landing at Nadzab"),
        (
            "{{s-ttl|title=[[Army|Commanding General Army]]}}",
            "Commanding General",
            "Army",
        ),
        ("{{Infobox ship|image=USS Banner at anchor.jpg}}", "USS", "USS Banner"),
        ("[[Hidden Person|Visible name]]", "Hidden", "Hidden Person"),
        ("[[File:USS Banner.jpg|USS Banner]]", "USS", "USS Banner"),
        ("<!-- John Smith -->", "John", "John Smith"),
    ],
)
def test_hidden_or_template_roles_supply_no_generic_identity_evidence(
    tmp_path, raw, word, label
):
    _, rows, spans, _, _ = run_prepare(tmp_path, raw, [{"word": word}], [ent(label)])
    assert rows[0]["word"] == word
    assert rows[0]["source_candidate_qids"] == []
    assert all(
        not span["source_row_indices"] and not span["qid_guided"] for span in spans
    )


@pytest.mark.parametrize(
    "raw,word,surface",
    [
        (
            "[[Fort Belvoir|Fort Humphreys, Virginia]]",
            "Virginia",
            "Fort Humphreys, Virginia",
        ),
        (
            "[[Treasury bill|U.S. Treasury bills]]",
            "U.S. Treasury",
            "U.S. Treasury bills",
        ),
        ("[[Battle|Recapture of Guam]]", "Guam", "Recapture of Guam"),
        (
            "[[List|List of World War II ships]]",
            "World War II",
            "List of World War II ships",
        ),
    ],
)
def test_complete_phrase_inside_longer_anchor_retains_evidence_without_repair(
    tmp_path, raw, word, surface
):
    _, rows, _, _, _ = run_prepare(tmp_path, raw, [{"word": word}], [ent(surface)])
    assert rows[0]["word"] == word
    assert rows[0]["repair_status"] == "source_context_review"
    assert rows[0]["source_candidate_qids"] == ["Q1"]
    assert rows[0]["repair_alternatives"] == [surface]


@pytest.mark.parametrize(
    "raw,word,surface",
    [("I-25 sailed.", "I", "I-25"), ("[[Nadzab]] was occupied.", "Na", "Nadzab")],
)
def test_lexically_cut_prose_and_anchor_names_can_still_expand(
    tmp_path, raw, word, surface
):
    _, rows, _, _, _ = run_prepare(tmp_path, raw, [{"word": word}], [ent(surface)])
    assert rows[0]["word"] == surface
    assert rows[0]["repair_status"] == "repaired"
    assert rows[0]["source_candidate_qids"] == ["Q1"]


@pytest.mark.parametrize("group", ["PER", "LOC"])
def test_ship_target_with_incompatible_original_type_retains_source_qid(
    tmp_path, group
):
    raw = "{{USS|Lindsey|DD-771}}"
    evidence = [
        {
            "page_id": 1,
            "revision_id": 2,
            "raw_start": 0,
            "raw_end": len(raw),
            "raw_text": raw,
            "target_title": "USS Lindsey (DD-771)",
            "qid": "Q1",
        }
    ]
    _, rows, _, _, _ = run_prepare(
        tmp_path, raw, [{"word": "Lindsey", "entity_group": group}], [], evidence
    )
    assert rows[0]["word"] == "Lindsey"
    assert rows[0]["entity_group"] == group
    assert rows[0]["repair_status"] == "source_type_review"
    assert rows[0]["source_candidate_qids"] == ["Q1"]


def test_review_link_in_verified_name_field_keeps_review_gate(tmp_path):
    raw = "{{Infobox person|name=[[John Smith]]}}"
    link = "[[John Smith]]"
    start = raw.index(link)
    evidence = [
        {
            "page_id": 1,
            "revision_id": 2,
            "raw_start": start,
            "raw_end": start + len(link),
            "raw_text": link,
            "target_title": "John Smith",
            "qid": None,
            "recovery_status": "REVIEW_OR_NO_QID",
        }
    ]
    _, rows, _, _, _ = run_prepare(tmp_path, raw, [{"word": "John"}], [], evidence)
    assert rows[0]["word"] == "John"
    assert rows[0]["repair_status"] == "source_target_review"


@pytest.mark.parametrize(
    "markup",
    [
        "''John Smith''",
        "'''John Smith'''",
        "'''''John Smith'''''",
        "<b>John Smith</b>",
        '<span class="x">John Smith</span>',
    ],
)
def test_visible_formatting_tags_keep_literal_prose_offsets(tmp_path, markup):
    raw = "served with " + markup + "."
    _, rows, spans, _, _ = run_prepare(
        tmp_path, raw, [{"word": "Jo"}], [ent("John Smith")]
    )
    assert rows[0]["word"] == "John Smith"
    assert rows[0]["repair_status"] == "repaired"
    assert rows[0]["repaired_start"] == raw.index("John Smith")
    assert rows[0]["repaired_end"] == raw.index("John Smith") + len("John Smith")
    assert all(raw[s["raw_start"] : s["raw_end"]] == s["raw_text"] for s in spans)

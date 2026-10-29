"""Clean source text must retain the exact raw origin of every mention."""

import pytest

from GG_Data.entity_resolution.hundred_page_pilot.clean_source_text import (
    clean_text,
    map_mention,
)


def test_unknown_behavior_switch_is_preserved_for_review():
    raw = "Japan __JAPAN__ France"
    cleaned = clean_text(raw)
    assert cleaned.text == raw
    start = raw.index("__JAPAN__")
    assert map_mention(cleaned, start, start + len("__JAPAN__"))["status"] == "uncertain"
    assert clean_text("Japan__NOTOC__ France").text == "Japan France"


def mapped(raw, word, occurrence=0, **kwargs):
    starts = [i for i in range(len(raw)) if raw.startswith(word, i)]
    start = starts[occurrence]
    cleaned = clean_text(raw, **kwargs)
    result = map_mention(cleaned, start, start + len(word))
    return cleaned, result


def assert_visible(raw, word, occurrence=0, **kwargs):
    cleaned, result = mapped(raw, word, occurrence, **kwargs)
    assert result["status"] == "mapped", result
    assert cleaned.text[result["start"] : result["end"]] == word
    assert result["reason"]
    assert len(cleaned.origins) == len(cleaned.text)
    return cleaned, result


def test_duplicate_name_maps_to_its_own_occurrence():
    raw = "[[Japan|Japan]] met Japan."
    cleaned, result = assert_visible(raw, "Japan", occurrence=2)
    assert result["start"] == cleaned.text.rindex("Japan")
    _, hidden = mapped(raw, "Japan", occurrence=0)
    assert hidden["status"] == "excluded"
    assert hidden["start"] is None and hidden["end"] is None


def test_unicode_offsets_are_python_characters_and_end_exclusive():
    raw = "😀 [[Chūzan]] and 日本."
    cleaned, result = assert_visible(raw, "Chūzan")
    start = raw.index("Chūzan")
    assert cleaned.origins[result["start"] : result["end"]] == [
        (i, i + 1) for i in range(start, start + len("Chūzan"))
    ]
    assert_visible(raw, "日本")


def test_entity_decoding_keeps_raw_character_span():
    raw = "A &amp; B &#x65E5;."
    cleaned = clean_text(raw)
    assert cleaned.text == "A & B 日."
    for token, rendered in [("&amp;", "&"), ("&#x65E5;", "日")]:
        start = raw.index(token)
        result = map_mention(cleaned, start, start + len(token))
        assert result["status"] == "mapped"
        assert cleaned.text[result["start"] : result["end"]] == rendered
        assert cleaned.origins[result["start"]] == (start, start + len(token))


@pytest.mark.parametrize(
    "raw,visible,hidden",
    [
        ("Japan<!-- France --> sailed.", "Japan", "France"),
        ("Japan<ref name='a'>France</ref> sailed.", "Japan", "France"),
        ("Japan{{sfn|France|1996}} sailed.", "Japan", "France"),
        ("[[French Republic|France]] is here.", "France", "French Republic"),
    ],
)
def test_hidden_markup_has_no_fallback(raw, visible, hidden):
    assert_visible(raw, visible)
    cleaned, result = mapped(raw, hidden)
    assert result["status"] == "excluded"
    assert result["start"] is None and result["end"] is None
    assert hidden not in cleaned.text


def test_removed_duplicate_citation_cannot_map_to_article_occurrence():
    raw = "Japan<ref>Japan</ref>"
    cleaned, result = mapped(raw, "Japan", occurrence=1)
    assert cleaned.text.strip() == "Japan"
    assert result["status"] == "excluded"
    assert result["start"] is None and result["end"] is None


@pytest.mark.parametrize(
    "raw,word",
    [
        ("{{nowrap|Japan}} fought.", "Japan"),
        ("{{lang|ja|日本}} is a name.", "日本"),
        ("{{nihongo|Tokyo|東京|Tōkyō}} is a city.", "Tokyo"),
        ("{{Infobox country|name=Japan|capital=Tokyo}}", "Japan"),
        ("{|\n! Year !! Country\n|-\n| 1944 || Japan\n|}", "Japan"),
    ],
)
def test_known_visible_values_survive(raw, word):
    assert_visible(raw, word)


@pytest.mark.parametrize(
    "value,word",
    [
        ("{{sclass|Charles Lawrence|transport|1}}, after October 1944", "Charles Lawrence"),
        ("[[Kennebec class oiler|''Mattaponi''-class oiler]]", "Mattaponi"),
        ("VC2-S-AP3 Victory ship", "VC2-S-AP3"),
    ],
)
def test_ship_characteristics_class_is_factual_content(value, word):
    from GG_Data.entity_resolution.hundred_page_pilot.clean_source_text import _clean_page

    raw = "{{Infobox ship/characteristics|class=" + value + "|style=color:red}}"
    cleaned = _clean_page(raw)
    start = raw.index(word)
    result = map_mention(cleaned, start, start + len(word))
    assert result["status"] == "mapped"
    assert cleaned.text[result["start"] : result["end"]] == word
    assert "color:red" not in cleaned.text


def test_generic_infobox_class_remains_a_formatting_control():
    raw = "{{Infobox country|name=Japan|class=hidden-layout}}"
    cleaned = clean_text(raw)
    assert "Japan" in cleaned.text
    assert "hidden-layout" not in cleaned.text


def test_unknown_template_remains_uncertain():
    raw = "Before {{mystery|Japan}} after."
    cleaned, result = mapped(raw, "Japan")
    assert result["status"] == "uncertain"
    assert result["start"] is None and result["end"] is None
    assert "{{mystery|Japan}}" in cleaned.text
    assert cleaned.review_spans
    assert_visible(raw, "Before")
    assert_visible(raw, "after")


def test_partial_hidden_boundary_is_uncertain():
    raw = "[[Japan|Japan]]"
    cleaned = clean_text(raw)
    start = raw.index("Japan")
    result = map_mention(cleaned, start, raw.rindex("Japan") + len("Japan"))
    assert result["status"] == "uncertain"
    assert result["start"] is None and result["end"] is None


def test_explicit_intervals_preserve_adjacent_article_text():
    raw = "JapanFranceItaly"
    cleaned = clean_text(raw, excluded=[(5, 11)], uncertain=[(11, 16)])
    result = map_mention(cleaned, 0, 5)
    assert result["status"] == "mapped"
    assert cleaned.text[result["start"] : result["end"]] == "Japan"
    assert map_mention(cleaned, 5, 11)["status"] == "excluded"
    assert map_mention(cleaned, 11, 16)["status"] == "uncertain"
    assert map_mention(cleaned, 4, 6)["status"] == "uncertain"


@pytest.mark.parametrize("interval", [(-1, 2), (1, 8), (3, 2), (1, 1)])
@pytest.mark.parametrize("kind", ["excluded", "uncertain"])
def test_invalid_intervals_fail(interval, kind):
    with pytest.raises(ValueError):
        clean_text("Japan", **{kind: [interval]})


@pytest.mark.parametrize("start,end", [(-1, 2), (0, 6), (3, 2), (1, 1)])
def test_invalid_mention_offsets_fail(start, end):
    with pytest.raises(ValueError):
        map_mention(clean_text("Japan"), start, end)


def test_partial_entity_cannot_claim_full_decoded_character():
    raw = "A &amp; B"
    cleaned = clean_text(raw)
    result = map_mention(cleaned, raw.index("amp"), raw.index("amp") + 3)
    assert result["status"] == "uncertain"
    assert result["start"] is None and result["end"] is None


def test_mention_across_internal_removed_markup_is_uncertain():
    raw = "New<!-- hidden --> York"
    cleaned = clean_text(raw)
    result = map_mention(cleaned, 0, len(raw))
    assert "hidden" not in cleaned.text
    assert result["status"] == "uncertain"
    assert result["start"] is None and result["end"] is None


def wrapper_inputs(tmp_path, monkeypatch, raw, rows):
    import hashlib

    import pyarrow as pa
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot import clean_source_text as module

    raw_path = tmp_path / "raw.txt"
    raw_path.write_bytes(raw.encode("utf-8"))
    revisions = tmp_path / "revisions.parquet"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    record = dict(page_id=1, revision_id=2, wikitext_path=str(raw_path), sha256=digest)
    pq.write_table(pa.Table.from_pylist([record]), revisions)
    mentions = tmp_path / "input.parquet"
    complete = []
    for index, row in enumerate(rows):
        text = row.get("Text", raw)
        word = row.get("word", "Japan")
        start = row.get("start", text.index(word))
        complete.append(
            dict(
                source_row_index=index,
                page_id=1,
                revision_id=2,
                entity_group="LOC",
                Text=text,
                word=word,
                start=start,
                end=start + len(word),
                extra="preserved",
            )
            | row
        )
    pq.write_table(pa.Table.from_pylist(complete), mentions)
    monkeypatch.setattr(module, "validate_revision", lambda revision: raw)
    return module, mentions, revisions, complete, digest


def test_wrapper_preserves_rows_and_original_columns(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    raw = "Japan<ref>France</ref> &amp; Italy."
    module, mentions, revisions, original, digest = wrapper_inputs(
        tmp_path,
        monkeypatch,
        raw,
        [{"word": "Japan"}, {"word": "France"}, {"word": "&amp;"}],
    )
    output = tmp_path / "clean"
    summary = module.clean_mentions(mentions, revisions, output)
    rows = pq.read_table(output / "mentions.parquet").to_pylist()
    assert len(rows) == len(original)
    assert isinstance(summary, dict)
    assert (output / "summary.json").is_file()
    assert [row["clean_status"] for row in rows] == ["mapped", "excluded", "mapped"]
    for source, row in zip(original, rows):
        assert all(row[key] == value for key, value in source.items() if key != "word")
        assert row["word_original"] == source["word"]
        assert row["clean_revision_sha256"] == digest
        assert row["clean_source_status"] == "unique_raw_placement"
        if row["clean_status"] == "mapped":
            assert row["Text_clean"][row["clean_start"] : row["clean_end"]] == row["word"]
        else:
            assert row["clean_start"] is None and row["clean_end"] is None
    assert rows[2]["word"] == "&"


def test_wrapper_flags_unclean_context_outside_a_valid_mention(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    raw = "Japan {{mystery|country=France}}"
    module, mentions, revisions, _, _ = wrapper_inputs(
        tmp_path, monkeypatch, raw, [{"word": "Japan"}]
    )
    output = tmp_path / "clean"
    module.clean_mentions(mentions, revisions, output)
    row = pq.read_table(output / "mentions.parquet").to_pylist()[0]
    assert row["clean_status"] == "mapped"
    assert row["clean_text_needs_review"] is True


def test_wrapper_repeated_passage_has_no_guessed_source_placement(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    raw = "Japan is here. Japan is here."
    module, mentions, revisions, _, _ = wrapper_inputs(
        tmp_path,
        monkeypatch,
        raw,
        [{"Text": "Japan is here."}],
    )
    output = tmp_path / "clean"
    module.clean_mentions(mentions, revisions, output)
    row = pq.read_table(output / "mentions.parquet").to_pylist()[0]
    assert row["clean_status"] == "uncertain"
    assert row["clean_source_status"] == "nonunique_raw_placement"
    assert row["clean_start"] is None and row["clean_end"] is None
    assert row["Text_clean"] == "Japan is here."


def test_wrapper_inherits_source_citation_section(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    raw = "== History ==\nJapan fought.\n== Bibliography ==\nFrance Press."
    module, mentions, revisions, _, _ = wrapper_inputs(
        tmp_path,
        monkeypatch,
        raw,
        [{"Text": "France Press.", "word": "France"}],
    )
    output = tmp_path / "clean"
    module.clean_mentions(mentions, revisions, output)
    row = pq.read_table(output / "mentions.parquet").to_pylist()[0]
    assert row["clean_source_status"] == "unique_raw_placement"
    assert row["clean_status"] == "excluded"
    assert row["clean_start"] is None and row["clean_end"] is None


@pytest.mark.parametrize(
    "invalid", ["duplicate_rows", "duplicate_revisions", "missing_column", "existing_output"]
)
def test_wrapper_rejects_unsafe_inputs(tmp_path, monkeypatch, invalid):
    import pyarrow as pa
    import pyarrow.parquet as pq

    module, mentions, revisions, original, _ = wrapper_inputs(
        tmp_path,
        monkeypatch,
        "Japan",
        [{"word": "Japan"}],
    )
    output = tmp_path / "clean"
    if invalid == "duplicate_rows":
        pq.write_table(pa.Table.from_pylist(original * 2), mentions)
    elif invalid == "duplicate_revisions":
        records = pq.read_table(revisions).to_pylist()
        pq.write_table(pa.Table.from_pylist(records * 2), revisions)
    elif invalid == "missing_column":
        pq.write_table(pq.read_table(mentions).drop(["start"]), mentions)
    else:
        output.mkdir()
    with pytest.raises((ValueError, FileExistsError)):
        module.clean_mentions(mentions, revisions, output)


def test_nested_supported_markup_retains_exact_value_origins():
    raw = "{{Infobox country|name={{nowrap|[[Japan|日本]]}}|image=Japan.png}}"
    cleaned, result = assert_visible(raw, "日本")
    start = raw.index("日本")
    assert cleaned.origins[result["start"] : result["end"]] == [
        (start, start + 1),
        (start + 1, start + 2),
    ]
    assert "Japan.png" not in cleaned.text


def test_html_attribute_name_is_not_article_text():
    raw = '<span title="Japan">France</span> met France.'
    assert_visible(raw, "France", occurrence=0)
    cleaned, result = mapped(raw, "France", occurrence=1)
    assert result["start"] == cleaned.text.rindex("France")
    assert mapped(raw, "Japan")[1]["status"] == "excluded"


def test_citation_inside_known_template_is_removed():
    raw = "{{nowrap|Japan<ref>France</ref>}} Italy"
    assert_visible(raw, "Japan")
    assert mapped(raw, "France")[1]["status"] == "excluded"
    assert_visible(raw, "Italy")


def test_external_link_multiple_spaces_keeps_exact_title_origins():
    raw = "[https://example.org   France]"
    cleaned, result = assert_visible(raw, "France")
    start = raw.index("France")
    assert cleaned.origins[result["start"] : result["end"]] == [
        (i, i + 1) for i in range(start, start + 6)
    ]


def test_table_header_attribute_is_removed_and_visible_origins_are_exact():
    raw = '{|\n! colspan="10"| Japanese overseas assets in 1945\n|}'
    assert_visible(raw, "Japanese")
    assert mapped(raw, "colspan")[1]["status"] == "excluded"


@pytest.mark.parametrize(
    "raw,word",
    [
        ("{{ship|HMS|Victory|1765}}", "HMS"),
        ("{{ship|HMS|Victory|1765}}", "Victory"),
        ("{{ship|HMS|Victory|1765}}", "1765"),
        ("{{USS|Enterprise|CV-6}}", "Enterprise"),
        ("{{USS|Enterprise|CV-6}}", "CV-6"),
    ],
)
def test_ship_literal_components_have_exact_origins(raw, word):
    cleaned, result = assert_visible(raw, word)
    start = raw.index(word)
    assert cleaned.origins[result["start"] : result["end"]] == [
        (i, i + 1) for i in range(start, start + len(word))
    ]


def test_generated_ship_prefix_does_not_claim_raw_source():
    cleaned = clean_text("{{USS|Enterprise|CV-6}}")
    start = cleaned.text.index("USS")
    assert all(left == right for left, right in cleaned.origins[start : start + 3])


def test_wrapper_full_page_projection_table_header_and_nested_refs(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    raw = (
        '== History ==\n{|\n! colspan="10"| Japanese overseas assets in 1945\n|}\n'
        "{{nowrap|Japan<ref>{{cite book|title=France}}</ref>}} fought."
    )
    module, mentions, revisions, _, _ = wrapper_inputs(
        tmp_path,
        monkeypatch,
        raw,
        [
            {"Text": '! colspan="10"| Japanese overseas assets in 1945', "word": "Japanese"},
            {
                "Text": "{{nowrap|Japan<ref>{{cite book|title=France}}</ref>}} fought.",
                "word": "Japan",
            },
            {
                "Text": "{{nowrap|Japan<ref>{{cite book|title=France}}</ref>}} fought.",
                "word": "France",
            },
        ],
    )
    output = tmp_path / "clean"
    module.clean_mentions(mentions, revisions, output)
    rows = pq.read_table(output / "mentions.parquet").to_pylist()
    assert [row["clean_status"] for row in rows] == ["mapped", "mapped", "excluded"]
    for row in rows[:2]:
        assert row["Text_clean"][row["clean_start"] : row["clean_end"]] == row["word"]
    assert "colspan" not in rows[0]["Text_clean"]
    assert "France" not in rows[1]["Text_clean"]
    assert rows[2]["clean_start"] is None and rows[2]["clean_end"] is None


@pytest.mark.parametrize(
    "raw",
    [
        "{{ship|SS|Tjisalak}}",
        "{{ship|Japanese submarine|I-8}}",
        "{{USS|Hope|AH-7}}",
    ],
)
def test_ship_generated_separators_keep_origin_source_order(raw):
    cleaned = clean_text(raw)
    starts = [left for left, _ in cleaned.origins]
    assert starts == sorted(starts)


@pytest.mark.parametrize(
    "template,word",
    [
        ("{{ship|SS|Tjisalak}}", "Tjisalak"),
        ("{{ship|Japanese submarine|I-8}}", "I-8"),
        ("{{USS|Hope|AH-7}}", "AH-7"),
    ],
)
def test_wrapper_projects_ship_parameter_passage_without_reassignment(
    tmp_path, monkeypatch, template, word
):
    import pyarrow.parquet as pq

    raw = "Before " + template + " sailed after."
    module, mentions, revisions, original, _ = wrapper_inputs(
        tmp_path,
        monkeypatch,
        raw,
        [{"Text": template, "word": word}],
    )
    output = tmp_path / "clean"
    module.clean_mentions(mentions, revisions, output)
    row = pq.read_table(output / "mentions.parquet").to_pylist()[0]
    assert row["clean_status"] == "mapped"
    assert row["word"] == word
    assert row["word_original"] == word
    assert row["Text"] == original[0]["Text"]
    assert row["Text_clean"] == clean_text(template).text
    assert row["Text_clean"][row["clean_start"] : row["clean_end"]] == word


@pytest.mark.parametrize(
    "raw,target",
    [
        ("[[:Category:Japan|Japan]]", "Category:Japan"),
        ("[[:File:X.jpg|Japan]]", "File:X.jpg"),
    ],
)
def test_escaped_namespace_link_keeps_visible_label(raw, target):
    cleaned, result = assert_visible(raw, "Japan", occurrence=1 if "Category" in raw else 0)
    assert cleaned.text == "Japan"
    start = raw.index(target)
    assert map_mention(cleaned, start, start + len(target))["status"] == "excluded"


@pytest.mark.parametrize("raw", ["[[Category:Japan]]", "[[File:X.jpg|Japan]]"])
def test_unescaped_namespace_link_remains_excluded(raw):
    cleaned = clean_text(raw)
    assert cleaned.text == ""
    assert map_mention(cleaned, 0, len(raw))["status"] == "excluded"


@pytest.mark.parametrize("template", ["[[:Category:Japan|Japan]]", "[[:File:X.jpg|Japan]]"])
def test_wrapper_preserves_escaped_namespace_link_label(tmp_path, monkeypatch, template):
    import pyarrow.parquet as pq

    raw = "Before " + template + " after."
    start = template.rindex("Japan")
    module, mentions, revisions, _, _ = wrapper_inputs(
        tmp_path,
        monkeypatch,
        raw,
        [{"Text": template, "word": "Japan", "start": start, "end": start + 5}],
    )
    output = tmp_path / "clean"
    module.clean_mentions(mentions, revisions, output)
    row = pq.read_table(output / "mentions.parquet").to_pylist()[0]
    assert row["clean_status"] == "mapped"
    assert row["Text_clean"] == "Japan"
    assert row["Text_clean"][row["clean_start"] : row["clean_end"]] == "Japan"


@pytest.mark.parametrize(
    "raw",
    [
        "<div>Japan</div><div>France</div>",
        "<p>Japan</p><p>France</p>",
        "== Japan ==<p>France</p>",
    ],
)
def test_block_boundaries_do_not_merge_article_tokens(raw):
    cleaned = clean_text(raw)
    assert "JapanFrance" not in cleaned.text
    assert "\n" in cleaned.text
    assert cleaned.text.split() == ["Japan", "France"]
    starts = [left for left, _ in cleaned.origins]
    assert starts == sorted(starts)
    assert_visible(raw, "Japan")
    assert_visible(raw, "France")


def test_whole_page_preserves_unknown_template_literal_for_review():
    from GG_Data.entity_resolution.hundred_page_pilot.clean_source_text import _clean_page

    raw = "{{mystery|country=Japan}}"
    cleaned = _clean_page(raw)
    assert cleaned.text == raw
    assert cleaned.review_spans
    start = raw.index("Japan")
    assert map_mention(cleaned, start, start + 5)["status"] == "uncertain"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Countries: [[Japan]]: Asia.", "Countries: Japan: Asia."),
        ("[[Japan]]; [[France]]", "Japan; France"),
        ("A <b>Japan</b>: France", "A Japan: France"),
    ],
)
def test_whole_page_inline_punctuation_is_not_list_markup(raw, expected):
    from GG_Data.entity_resolution.hundred_page_pilot.clean_source_text import _clean_page

    cleaned = _clean_page(raw)
    assert cleaned.text == expected

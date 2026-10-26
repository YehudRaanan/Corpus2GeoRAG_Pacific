"""Protect source attribution and raw-row preservation."""

import attach_source_page_ids as subject
import pandas as pd
import pyarrow as pa


def test_full_passage_matches_without_fuzzy_edits():
    page = {
        "status": "ARTICLE",
        "pageid": 42,
        "extract": "Intro. Cafe\u0301\n  Alpha beta. End.",
    }
    assert subject.match_text("Café Alpha beta.", page) == (42, "VERIFIED_NORMALIZED")
    assert subject.match_text("Alpha beta.", page) == (42, "VERIFIED_EXACT")
    assert subject.match_text("alpha beta.", page) == (None, "TEXT_NOT_FOUND")
    assert subject.match_text("Alpha-beta.", page) == (None, "TEXT_NOT_FOUND")
    assert subject.match_text("", page) == (None, "EMPTY_TEXT")


def test_redirects_and_unsafe_pages():
    response = {
        "query": {
            "normalized": [{"from": "old_title", "to": "Old title"}],
            "redirects": [{"from": "Old title", "to": "New title"}],
            "pages": [
                {"title": "New title", "pageid": 9, "ns": 0, "extract": "Copied text"}
            ],
        }
    }
    page = subject.resolve_page("old_title", response)
    assert page["pageid"] == 9 and page["status"] == "ARTICLE"
    assert page["title"] == "New title"
    response["query"]["pages"][0]["pageprops"] = {"disambiguation": ""}
    page = subject.resolve_page("old_title", response)
    assert subject.match_text("Copied text", page) == (None, "DISAMBIGUATION")
    missing = subject.resolve_page(
        "Gone", {"query": {"pages": [{"title": "Gone", "missing": True}]}}
    )
    assert subject.match_text("Anything", missing) == (None, "MISSING_PAGE")


def test_rendered_text_removes_reference_markers_but_keeps_words():
    rendered = subject.render_text(
        '<p>Alpha <a>beta</a><sup class="reference">[1]</sup>.</p><p>Gamma</p><script>bad</script>'
    )
    assert subject.normalize(rendered) == "Alpha beta. Gamma"
    page = {"status": "ARTICLE", "pageid": 4, "extract": "", "rendered": rendered}
    assert subject.match_text("Alpha beta.", page) == (4, "VERIFIED_RENDERED")


def test_append_ids_preserves_duplicates_order_schema_and_nulls():
    table = pa.table(
        {
            "word": ["A", "B", "A"],
            "Source": ["One", "Two", "One"],
            "Text": ["First", "Other", "First"],
            "score": [0.8, 0.9, 0.8],
        }
    )
    table = table.replace_schema_metadata({b"provenance": b"raw"})
    decisions = {
        ("One", "First"): {"wiki_page_id": 7},
        ("Two", "Other"): {"wiki_page_id": None},
    }
    result = subject.append_ids(table, decisions)
    assert result.column_names == table.column_names + ["wiki_page_id"]
    assert result.select(table.column_names).equals(table, check_metadata=True)
    assert result["wiki_page_id"].type == pa.int64()
    assert result["wiki_page_id"].to_pylist() == [7, None, 7]


def test_missing_decision_is_an_error():
    table = pa.table({"Source": ["One"], "Text": ["First"]})
    try:
        subject.append_ids(table, {})
    except KeyError:
        pass
    else:
        raise AssertionError("Missing evidence must stop export")


def test_recovered_source_is_rechecked_against_final_candidate_pool(tmp_path):
    text = "This is a sufficiently long copied passage with eight distinct words."
    source = "Missing source"
    key = subject.hashlib.sha256(source.encode()).hexdigest()
    for directory in ["pages", "candidate_pages", "search_candidates"]:
        (tmp_path / directory).mkdir()
    subject.save_json(tmp_path / "pages" / f"{key}.json.gz", {"status": "MISSING_PAGE"})
    for number in [1, 2]:
        subject.save_json(
            tmp_path / "candidate_pages" / f"{number}.json.gz",
            {"status": "ARTICLE", "pageid": number, "extract": text},
        )
    subject.save_json(
        tmp_path / "search_candidates" / f"{key}.json",
        {"candidate_pages": ["candidate_pages/1.json.gz"]},
    )
    result = subject.make_decisions(
        pd.DataFrame({"Source": [source], "Text": [text]}), tmp_path
    )
    assert result[(source, text)]["wiki_page_id"] is None
    assert result[(source, text)]["status"] == "AMBIGUOUS_TEXT_MATCH"


def test_text_search_evidence_must_be_the_page_that_contains_the_passage():
    text = "This is a sufficiently long copied passage with eight distinct words."
    pages = {
        "one": {"status": "ARTICLE", "pageid": 8, "extract": "Other text"},
        "two": {"status": "ARTICLE", "pageid": 8, "extract": text},
    }
    result = subject.choose_evidence(text, pages)
    assert result["wiki_page_id"] == 8 and result["page_evidence"] == "two"
    pages["three"] = {"status": "ARTICLE", "pageid": 9, "extract": text}
    assert subject.choose_evidence(text, pages)["wiki_page_id"] is None


def test_text_search_accepts_only_one_full_passage_and_rejects_short_text():
    text = "This is a sufficiently long copied passage with eight distinct words."
    page = {"status": "ARTICLE", "pageid": 1, "extract": text}
    other = {"status": "ARTICLE", "pageid": 2, "extract": text}
    assert subject.search_decision(text, [page]) == (1, "VERIFIED_SEARCH_EXACT")
    assert subject.search_decision(text, [page, page]) == (1, "VERIFIED_SEARCH_EXACT")
    assert subject.search_decision(text, [page, other]) == (
        None,
        "AMBIGUOUS_TEXT_MATCH",
    )
    assert subject.search_decision("war", [page]) == (
        None,
        "INSUFFICIENT_TEXT_FOR_SEARCH",
    )
    assert subject.search_decision(text + " Changed.", [page]) == (
        None,
        "TEXT_NOT_FOUND",
    )

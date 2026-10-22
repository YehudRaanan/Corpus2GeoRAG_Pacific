"""Regression: name equality must never add a QID to source-page evidence."""

import copy

import pytest

from bilingual_page_pilot import read
from direct_wikidata_pilot import PAGE_CANDIDATE_SCOPE, page_candidate_ids
from full_direct_wikidata import match_page, run, save


def test_page_candidates_exclude_saved_global_hits_and_preserve_languages():
    articles = [
        {
            "qid": "Q1",
            "links": [{"qid": "Q84"}],
            "pool": ["Q1001456"],
            "searches": [{"hits": [{"id": "Q1001456"}]}],
        },
        {"qid": "Q1", "links": [{"qid": "Q2"}]},
    ]
    assert page_candidate_ids(articles) == {"Q1", "Q84", "Q2"}
    metadata = {
        q: {"label": "London", "aliases": [], "direct_types": ["Q618123"]}
        for q in ["Q84", "Q1001456"]
    }
    row = {
        "mention_id": "mention-london",
        "raw": {"word": "London", "entity_group": "LOC"},
        "attempts": [],
    }
    _, _, matched = match_page("Example", [copy.deepcopy(row)], {"Q84"}, metadata)
    assert matched[0]["assigned_id"] == "Q84"
    assert matched[0]["attempts"][0]["tied_ids"] == ["Q84"]


def test_historical_completed_run_cannot_bypass_scope_check(tmp_path):
    save(tmp_path / "manifest.json", {"outputs": {}})
    with pytest.raises(ValueError, match="Historical matching scope"):
        run(tmp_path)


def test_current_scope_is_required_on_completed_run(tmp_path):
    save(
        tmp_path / "manifest.json",
        {"page_candidate_scope": PAGE_CANDIDATE_SCOPE, "outputs": {}},
    )
    save(tmp_path / "summary.json", {"mentions": 1})
    assert run(tmp_path) == read(tmp_path / "summary.json")

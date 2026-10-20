"""The 5% boundary is inclusive; missing counts never become zero scores."""

import pytest

from GG_Data.pipeline.scope_concentration_filter import threshold_rows


def test_five_percent_boundary_and_invalid_id_or_missing_denominator():
    def row(qid, numerator, denominator):
        return {
            "qid": qid,
            "scope_linking_pages": numerator,
            "all_linking_pages": denominator,
            "relevance": numerator / denominator if denominator else None,
        }

    inputs = [row("Q1", 49, 1000), row("Q2", 5, 100), row("Q3", 51, 1000)]
    assert [r["keep_for_event_retrieval"] for r in threshold_rows(inputs)] == [
        False,
        True,
        True,
    ]
    assert all("keep_for_event_retrieval" not in r for r in inputs)
    with pytest.raises(ValueError, match="synthetic"):
        threshold_rows([row("SYN_1", 1, 1)])
    with pytest.raises(ValueError, match="Unknown"):
        threshold_rows([row("Q1", 0, None)])


def test_language_scores_are_independent_and_unavailable_is_not_zero():
    rows = [
        dict(
            qid="Q1",
            wiki="enwiki",
            scope_linking_pages=1,
            all_linking_pages=100,
            relevance=0.01,
            score_status="SCORED",
        ),
        dict(
            qid="Q1",
            wiki="jawiki",
            scope_linking_pages=1,
            all_linking_pages=10,
            relevance=0.1,
            score_status="SCORED",
        ),
        dict(
            qid="Q2",
            wiki="enwiki",
            scope_linking_pages=None,
            all_linking_pages=None,
            relevance=None,
            score_status="UNAVAILABLE_SNAPSHOT_PAGE",
        ),
        dict(
            qid="Q2",
            wiki="jawiki",
            scope_linking_pages=1,
            all_linking_pages=20,
            relevance=0.05,
            score_status="SCORED",
        ),
    ]
    assert [r["keep_for_event_retrieval"] for r in threshold_rows(rows)] == [
        False,
        True,
        None,
        True,
    ]
    with pytest.raises(ValueError, match="unique"):
        threshold_rows([rows[0], rows[0]])

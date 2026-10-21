"""One entity counts once; unknown is not zero or an observed-subset mean."""

import pytest

from GG_Data.pipeline.event_linked_entity_relevance_probe import summarize_events


def test_distinct_entities_equal_weight_and_missing_score():
    event = dict(qid="Q10", eligible=True, daniel_qids=["Q1", "Q2", "Q2"])
    scores = [
        dict(
            qid="Q1", maximum_relevance=0.1, scope_linking_pages=1, all_linking_pages=10
        ),
        dict(
            qid="Q2", maximum_relevance=0.3, scope_linking_pages=3, all_linking_pages=10
        ),
    ]
    row = summarize_events([event], scores)[0]
    assert row["linked_entity_count"] == 2
    assert (row["min_relevance"], row["mean_relevance"], row["max_relevance"]) == (
        0.1,
        0.2,
        0.3,
    )
    scores[1].update(
        maximum_relevance=None, scope_linking_pages=None, all_linking_pages=None
    )
    row = summarize_events([event], scores)[0]
    assert row["unknown_entity_qids"] == ["Q2"]
    assert row["scored_entity_count"] == 1
    assert row["mean_relevance"] is row["min_relevance"] is row["max_relevance"] is None
    with pytest.raises(ValueError, match="no score record"):
        summarize_events([event], scores[:1])

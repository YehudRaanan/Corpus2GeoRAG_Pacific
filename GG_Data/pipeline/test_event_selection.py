"""Population S2T 7: three distinct retained QIDs; no Event score gate."""

import pytest

from GG_Data.pipeline.event_selection import select_events


def test_three_distinct_qids_and_recognition_without_scores():
    rows = select_events(
        [
            dict(qid="Q10", event_hierarchy_match=True, daniel_qids=["Q1", "Q2", "Q2"]),
            dict(qid="Q11", event_hierarchy_match=True, daniel_qids=["Q1", "Q2", "Q3"]),
            dict(
                qid="Q12", event_hierarchy_match=False, daniel_qids=["Q1", "Q2", "Q3"]
            ),
        ],
        {"Q1", "Q2", "Q3"},
    )
    assert [r["keep_event"] for r in rows] == [False, True, False]
    assert rows[0]["linked_entity_count"] == 2
    assert all(r["event_threshold_percent"] is None for r in rows)
    with pytest.raises(ValueError, match="outside retained"):
        select_events(
            [dict(qid="Q10", event_hierarchy_match=True, daniel_qids=["Q9"])], {"Q1"}
        )
    with pytest.raises(ValueError, match="unique Events"):
        select_events(
            [dict(qid="Q10", event_hierarchy_match=None, daniel_qids=[])], set()
        )

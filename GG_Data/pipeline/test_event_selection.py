"""S2T 6.1: the Event cutoff includes 2%; missing evidence stays undecided."""

from GG_Data.pipeline.event_selection import select_events


def test_event_threshold_exact_boundary_and_unknown():
    scores = [
        dict(
            qid="Q1",
            maximum_relevance=0.02,
            scope_linking_pages=1,
            all_linking_pages=50,
        ),
        dict(
            qid="Q2",
            maximum_relevance=0.01,
            scope_linking_pages=1,
            all_linking_pages=100,
        ),
        dict(
            qid="Q3",
            maximum_relevance=0.019,
            scope_linking_pages=19,
            all_linking_pages=1000,
        ),
        dict(
            qid="Q4",
            maximum_relevance=None,
            scope_linking_pages=None,
            all_linking_pages=None,
        ),
    ]
    events = [
        dict(qid="Q10", eligible=True, daniel_qids=["Q1", "Q2", "Q2"]),
        dict(qid="Q11", eligible=True, daniel_qids=["Q2", "Q3"]),
        dict(qid="Q12", eligible=True, daniel_qids=["Q1", "Q4"]),
    ]
    rows = select_events(events, scores)
    assert [r["keep_event"] for r in rows] == [True, False, None]
    assert rows[0]["linked_entity_count"] == 2
    assert rows[2]["unknown_entity_qids"] == ["Q4"]
    assert rows[2]["max_relevance"] is None

"""Check score lineage, uncapped Events and the strict mutual assertion budget."""

import copy

import pytest

from GG_Data.pipeline.relation_selection import attach_importance, importance, select
from GG_Data.pipeline.relations import SourceException


def edge(index, subject, target):
    return dict(
        observation_id=str(index), subject_entity_id=subject, object_entity_id=target
    )


def test_counts_original_mentions_and_source_pages_without_type_or_counterpart_fanout():
    mentions = [
        dict(
            mention_id=str(i), entity_id=qid, raw=dict(entity_group=kind, Source=source)
        )
        for i, (qid, kind, source) in enumerate(
            [
                ("Q1", "ORG", "Page A"),
                ("Q1", "LOC", "Page A"),
                ("Q1", "ORG", "Page B"),
                ("Q2", "DATE", "Page A"),
                ("SYN_3", "LOC", "Page C"),
            ]
        )
    ]
    assert importance(mentions) == {
        "Q1": dict(
            distinct_source_pages=2,
            total_mentions=3,
            score=6,
            source_pages=["Page A", "Page B"],
        )
    }
    with pytest.raises(SourceException, match="Repeated original mention"):
        importance(mentions + [mentions[0]])


def test_mutual_selection_no_refill_event_exemption_and_source_preservation():
    # Q1 chooses Q2, but Q2 has 20 stronger neighbors and rejects this assertion.
    rows = [edge(0, "Q1", "Q2")]
    rows += [edge(i, "Q2", f"Q{100+i}") for i in range(1, 21)]
    rows += [edge(30 + i, "Q3", f"Q{200+i}") for i in range(21)]
    rows += [edge(90, "Q3", "Q4"), edge(91, "Q2", "Q2")]
    scores = {
        qid: dict(score=int(qid[1:]))
        for row in rows
        for qid in (row["subject_entity_id"], row["object_entity_id"])
    }
    original = copy.deepcopy(rows)
    kept, audit = select(rows, scores, {"Q3", "Q4"}, event_population_complete=True)
    assert rows == original
    assert "0" not in {row["observation_id"] for row in kept}
    assert len([row for row in kept if row["subject_entity_id"] == "Q3"]) == 22
    assert len([row for row in kept if row["subject_entity_id"] == "Q2"]) == 20
    assert audit[0]["endpoint_selections"] == {"Q1": True, "Q2": False}
    with pytest.raises(SourceException, match="Complete Event membership"):
        select(rows, scores, set(), event_population_complete=False)


def test_equal_cutoff_scores_stop_and_multiple_assertions_spend_separate_slots():
    rows = [edge(i, "Q1", "Q2") for i in range(21)]
    scores = {"Q1": dict(score=1), "Q2": dict(score=2)}
    with pytest.raises(SourceException, match="Unapproved importance tie"):
        select(rows, scores, set(), event_population_complete=True)
    kept, _ = select(rows[:20], scores, set(), event_population_complete=True)
    assert kept == rows[:20]
    with pytest.raises(SourceException, match="unique base assertions"):
        select(rows[:1] * 2, scores, set(), event_population_complete=True)
    with pytest.raises(SourceException, match="Missing Daniel importance"):
        select(rows[:1], {}, set(), event_population_complete=True)


def test_entity_score_preserves_types_raw_evidence_and_synthetic_null():
    rows = [
        dict(entity_id=qid, type=kind, attributes={"original": ["evidence"]})
        for qid, kind in [("Q1", "LOC"), ("Q1", "ORG"), ("SYN_1", "MISC")]
    ]
    original = copy.deepcopy(rows)
    scores = {"Q1": dict(distinct_source_pages=2, total_mentions=3, score=6)}
    result = attach_importance(rows, scores, "population-hash")
    assert rows == original
    assert [r["importance"] for r in result] == [6, 6, None]
    for prior, current in zip(original, result):
        assert current["attributes"]["original"] == prior["attributes"]["original"]
        assert current["entity_id"] == prior["entity_id"]
        assert current["type"] == prior["type"]
        assert (
            current["attributes"]["importance_basis"]["population_sha256"]
            == "population-hash"
        )
    assert (
        result[-1]["attributes"]["importance_basis"]["status"] == "SYNTHETIC_UNRESOLVED"
    )
    with pytest.raises(SourceException, match="Entity importance missing"):
        attach_importance(rows, {}, "population-hash")
    with pytest.raises(SourceException, match="Repeated Entity identity"):
        attach_importance(rows + rows[:1], scores, "population-hash")
    with pytest.raises(SourceException, match="already supplied"):
        attach_importance(result, scores, "population-hash")

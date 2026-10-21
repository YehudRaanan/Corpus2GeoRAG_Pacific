"""Population S2T 7: two distinct QIDs, 2% or explicit unknown score."""

from fractions import Fraction
import pytest
from GG_Data.pipeline.event_selection import select_events


@pytest.mark.parametrize(
    "endpoints,recognized,scores,keep,reason",
    [
        (
            ["Q1", "Q2"],
            True,
            {"Q1": Fraction(1, 50), "Q2": Fraction(0)},
            True,
            "KNOWN_MAXIMUM_AT_LEAST_2PCT",
        ),
        (
            ["Q1", "Q2"],
            True,
            {"Q1": Fraction(199, 10000), "Q2": Fraction(0)},
            False,
            "ALL_SCORED_BELOW_2PCT",
        ),
        (
            ["Q1", "Q2"],
            True,
            {"Q1": Fraction(0), "Q2": None},
            True,
            "UNSCORED_LINKED_ENTITY_EXCEPTION",
        ),
        (
            ["Q1", "Q2"],
            True,
            {"Q1": None, "Q2": None},
            True,
            "UNSCORED_LINKED_ENTITY_EXCEPTION",
        ),
        (
            ["Q1", "Q1"],
            True,
            {"Q1": None},
            False,
            "FEWER_THAN_TWO_DISTINCT_DANIEL_QIDS",
        ),
        (["Q1", "Q2"], False, {"Q1": None, "Q2": None}, False, "NOT_RECOGNIZED"),
        (
            ["Q1", "Q2"],
            True,
            {"Q1": Fraction(1, 50), "Q2": None},
            True,
            "KNOWN_MAXIMUM_AT_LEAST_2PCT",
        ),
    ],
)
def test_event_gate(endpoints, recognized, scores, keep, reason):
    row = select_events(
        [dict(qid="Q10", event_hierarchy_match=recognized, daniel_qids=endpoints)],
        {"Q1", "Q2"},
        scores,
    )[0]
    assert row["keep_event"] is keep
    assert row["decision_reason"] == reason
    assert row["linked_entity_count"] == len(set(endpoints))
    assert row["unscored_exception_used"] is (
        reason == "UNSCORED_LINKED_ENTITY_EXCEPTION"
    )


def test_missing_record_is_not_an_unknown_score():
    with pytest.raises(ValueError, match="explicit exact scores"):
        select_events(
            [dict(qid="Q10", event_hierarchy_match=True, daniel_qids=["Q1", "Q2"])],
            {"Q1", "Q2"},
            {"Q1": None},
        )


def test_scope_and_recognition_are_required():
    with pytest.raises(ValueError, match="outside retained"):
        select_events(
            [dict(qid="Q10", event_hierarchy_match=True, daniel_qids=["Q9"])],
            {"Q1"},
            {"Q9": None},
        )
    with pytest.raises(ValueError, match="unique Events"):
        select_events(
            [dict(qid="Q10", event_hierarchy_match=None, daniel_qids=[])], set(), {}
        )

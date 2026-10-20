"""The benchmark must count distinct Daniel IDs across both directions."""

import pytest

from GG_Data.pipeline import events
from GG_Data.pipeline.event_on_demand import event_path
from GG_Data.pipeline.event_timing_sample import (
    candidate_endpoints,
    native_rank_answers,
)
from GG_Data.pipeline.relations import SourceException


def test_candidate_union_requires_two_distinct_daniel_endpoints():
    outgoing = {"Q10": {"Q1"}, "Q11": {"Q1", "Q2"}, "Q12": {"Q1"}}
    incoming = [
        {"id": "Q10", "targets": ["Q2", "Q2"]},
        {"id": "Q12", "targets": ["Q1"]},
    ]
    assert candidate_endpoints(incoming, outgoing, {"Q1", "Q2"}) == {
        "Q10": ["Q1", "Q2"],
        "Q11": ["Q1", "Q2"],
    }
    with pytest.raises(SourceException):
        candidate_endpoints([{"id": "Q10", "targets": ["Q3"]}], outgoing, {"Q1", "Q2"})


def test_cached_rank_uri_cannot_reintroduce_a_deprecated_event_path():
    saved = {
        "P31": {
            "Q30": [
                {"parent": "Q100", "rank": "http://wikiba.se/ontology#PreferredRank"}
            ]
        },
        "P279": {
            "Q100": [
                {
                    "parent": events.EVENT_ROOT,
                    "rank": "http://wikiba.se/ontology#DeprecatedRank",
                }
            ]
        },
    }
    adapted = native_rank_answers(saved)
    assert adapted["P31"]["Q30"][0]["rank"] == "preferred"
    assert adapted["P279"]["Q100"][0]["rank"] == "deprecated"
    assert event_path("Q100", adapted["P279"], {}, None) is None
    assert events.classify_events(saved) == events.classify_events(adapted)
    assert saved["P279"]["Q100"][0]["rank"].endswith("#DeprecatedRank")

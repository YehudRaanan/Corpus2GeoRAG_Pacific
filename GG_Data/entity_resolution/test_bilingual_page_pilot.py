"""Small checks for the agreed decision rules, independent of live services."""

import random
from unittest.mock import Mock

import pytest

from bilingual_page_pilot import LiveData, categories, choose, read, synthetic_id
from generate_candidates import NameIndex


@pytest.mark.parametrize("post", [False, True])
def test_saved_responses_survive_new_client_without_network(tmp_path, post):
    url = "https://www.wikidata.org/w/api.php"
    params = {"action": "wbgetentities", "ids": "Q5"}
    payload = {"entities": {"Q5": {"id": "Q5", "labels": {}}}}
    first = LiveData(tmp_path)
    response = Mock(status_code=200)
    response.json.return_value = payload
    first.session.request = Mock(return_value=response)
    assert first.get(url, params, post=post) == payload
    first.session.request.assert_called_once()
    saved_path = next(tmp_path.glob("*.json.gz"))
    assert read(saved_path)["data"] == payload

    replay = LiveData(tmp_path)
    replay.session.request = Mock(side_effect=AssertionError("Network is disabled"))
    assert replay.get(url, dict(reversed(list(params.items()))), post=post) == payload
    replay.session.request.assert_not_called()
    assert replay.requests[0]["retrieved_at"] == first.requests[0]["retrieved_at"]


def test_decision_rules():
    metadata = {
        "Q1": {"label": "Tanaka", "aliases": ["田中"], "direct_types": ["Q5"]},
        "Q2": {"label": "Tanaka", "direct_types": ["Q5"]},
        "Q3": {"label": "Tanaka", "direct_types": ["Q43229"]},
        "Q4": {"label": "Tanaka", "direct_types": []},
        "Q5": {"parents": []},
        "Q43229": {"parents": []},
    }
    index = NameIndex(["Q1", "Q2", "Q3", "Q4"], metadata)
    candidates = index.find("Tanaka", "MISC", 0.8)
    result = choose(candidates, "PER", metadata, random.Random(42))
    assert result["tied_ids"] == ["Q1", "Q2"]
    assert result == choose(candidates, "PER", metadata, random.Random(42))
    assert (
        choose(index.find("田中", "MISC", 0.8), "PER", metadata, random.Random(42))[
            "entity_id"
        ]
        == "Q1"
    )
    assert (
        choose(candidates, "LOC", metadata, random.Random(42))["status"]
        == "TYPE_MISMATCH"
    )
    assert (
        choose(
            [c for c in candidates if c["entity_id"] == "Q4"],
            "PER",
            metadata,
            random.Random(42),
        )["status"]
        == "TYPE_UNKNOWN"
    )
    # Type-filter first: a lower compatible score beats a higher incompatible score.
    reduced = [
        {**c, "name_similarity": 0.81 if c["entity_id"] == "Q1" else 0.99}
        for c in candidates
        if c["entity_id"] in {"Q1", "Q3"}
    ]
    assert choose(reduced, "PER", metadata, random.Random(1))["entity_id"] == "Q1"
    two_people = [
        {**c, "name_similarity": 0.81 if c["entity_id"] == "Q1" else 0.99}
        for c in candidates
        if c["entity_id"] in {"Q1", "Q2"}
    ]
    assert choose(two_people, "PER", metadata, random.Random(1))["entity_id"] == "Q2"
    assert (
        choose([], "PER", metadata, random.Random(1))["status"]
        == "NO_NAME_ABOVE_THRESHOLD"
    )
    assert categories(metadata["Q4"], metadata) == set()
    assert synthetic_id(
        {"mention_id": "mention-" + "a" * 64}, "TYPE_MISMATCH"
    ).startswith("SYN_TYPE_")
    assert synthetic_id(
        {"mention_id": "mention-" + "a" * 64}, "NO_NAME_ABOVE_THRESHOLD"
    ) != synthetic_id({"mention_id": "mention-" + "b" * 64}, "NO_NAME_ABOVE_THRESHOLD")


def test_type_inheritance_and_exclusions():
    metadata = {
        "unit_class": {"parents": ["Q176799", "cycle"]},
        "cycle": {"parents": ["unit_class"]},
        "year_class": {"parents": ["Q577"]},
        "place_class": {"parents": ["Q618123"]},
        "role_class": {"parents": []},
    }
    assert categories({"direct_types": ["unit_class"]}, metadata) == {"ORG"}
    assert categories({"direct_types": ["year_class"]}, metadata) == {"DATE"}
    assert categories({"direct_types": ["Q47018901"]}, metadata) == {"DATE"}
    assert categories({"direct_types": ["place_class"]}, metadata) == {"LOC"}
    assert categories({"direct_types": ["role_class"]}, metadata) == {"MISC"}
    assert categories({"direct_types": ["Q4167410"]}, metadata) == set()

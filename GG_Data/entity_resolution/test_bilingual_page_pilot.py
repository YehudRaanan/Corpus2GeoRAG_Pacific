"""Small checks for the agreed decision rules, independent of live services."""

import random

from bilingual_page_pilot import categories, choose, synthetic_id
from generate_candidates import NameIndex


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

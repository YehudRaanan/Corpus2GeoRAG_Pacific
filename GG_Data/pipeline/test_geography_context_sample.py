"""Context clues must be local evidence, never borrowed from other names."""

import pytest

from GG_Data.pipeline.geography_context_sample import (
    checked_context,
    compatible,
    context,
    exact_alias,
    parent_labels,
)


def mention(text: str, name: str) -> dict:
    start = text.index(name)
    return dict(
        Text=text, word=name, start=start, end=start + len(name), mention_id="test"
    )


def test_context_preserves_literal_evidence_without_borrowing_other_places():
    text = (
        "Crew trained at Example Army Air Base in Idaho. Pilots used another airfield."
    )
    result = context(mention(text, "Example Army Air Base"))
    assert {f["value"] for f in result["features"]} == {"airport"}
    assert result["parents"][0]["value"] == "Idaho"
    for evidence in result["features"] + result["parents"]:
        assert text[evidence["start"] : evidence["end"]] == evidence.get(
            "literal", evidence.get("value")
        )
    assert not context(mention("Example Town, where troops landed.", "Example Town"))[
        "parents"
    ]
    assert not context(
        mention("Hoosick Falls, New York. Another airfield exists.", "Hoosick Falls")
    )["features"]
    assert (
        context(mention("Piva Yoke fighter strip", "Piva Yoke"))["features"][0]["value"]
        == "airport"
    )
    broken = mention("Example Town", "Example Town") | {"end": 2}
    with pytest.raises(ValueError, match="span"):
        context(broken)


def test_candidate_cannot_supply_its_own_missing_input_context():
    candidate = dict(
        source="GeoNames", country_code="US", admin1="NY", feature_code="PPL"
    )
    assert parent_labels(candidate, {("US", "NY"): ["New York"]}) == ["New York"]
    assert not compatible("peninsula", candidate)
    assert compatible("settlement", candidate)
    assert exact_alias("Donbaik", ["Done Paik", "Donbaik"])
    assert not exact_alias("Crabbs Peninsula", ["Crabs Peninsula"])


def test_parent_gate_rejects_person_clue_and_keeps_supported_region():
    clue = context(mention("For the assault on Donbaik, Lloyd planned it.", "Donbaik"))
    candidate = dict(source="GeoNames", source_id="1", country_code="MM", admin1="01")
    checked = checked_context(clue, [candidate], {("MM", "01"): ["Rakhine"]})
    assert not checked["parents"]
    assert checked["rejected_parents"][0]["value"] == "Lloyd"
    assert clue["parents"][0]["value"] == "Lloyd"  # Original evidence unchanged.
    positive = context(mention("Hoosick Falls, New York.", "Hoosick Falls"))
    candidate = candidate | dict(country_code="US", admin1="NY")
    checked = checked_context(positive, [candidate], {("US", "NY"): ["New York"]})
    assert checked["parents"][0]["value"] == "New York"
    assert checked["parents"][0]["supporting_candidates"][0]["source_id"] == "1"
    assert not checked["rejected_parents"]
    assert not checked_context(positive, [], {})["parents"]

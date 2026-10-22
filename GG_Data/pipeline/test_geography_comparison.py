"""The comparison cannot change its population or count broken responses as misses."""

import pytest

from GG_Data.pipeline.geography_comparison import (
    candidate_profile,
    query_for,
    sample_targets,
    validate_response,
)


def test_frozen_sample_keeps_poor_inputs_and_is_order_independent():
    originals = [dict(place_id=f"Q{i}", name=".") for i in range(1, 11)]
    targets = originals + [dict(place_id=f"Q{i}") for i in range(11, 61)]
    targets += [dict(place_id=f"SYN_{i}") for i in range(50)]
    result = sample_targets(targets, originals)
    assert result == sample_targets(list(reversed(targets)), originals)
    assert len(result) == len({r["place_id"] for r in result}) == 40
    assert [r["name"] for r in result[:10]] == ["."] * 10
    assert sum(r["cohort"] == "random_qid" for r in result) == 15
    assert sum(r["cohort"] == "random_synthetic" for r in result) == 15


def test_query_uses_native_context_and_keeps_diagnostic_date_arms_separate():
    place = dict(name="Example", selection_date="1945")
    dated = query_for(place, ["GB"], True)
    native = query_for(place, ["GB"], False)
    assert dated["start"] == dated["end"] == 1945
    assert "countries" not in dated
    assert native["query"] == "Example" and native["countries"] == ["GB"]
    assert "start" not in native and "end" not in native
    assert "countries" not in query_for(place, [], False)


def test_missing_or_failed_queries_are_not_zero_candidate_results():
    validate_response({"a": {"result": []}}, {"a": {}})
    for response in [
        {},
        {"a": {}},
        {"a": {"result": [], "error": "failure"}},
        {"a": {"result": [{}]}},
    ]:
        with pytest.raises(ValueError):
            validate_response(response, {"a": {}})


def test_perfect_name_score_and_reference_agreement_do_not_accept_geometry():
    rows = [
        dict(id="place:gn:wrong", name="London", score=100, confidence=100),
        dict(id="place:wd:Q84", name="London", score=100, confidence=100),
    ]
    profile = candidate_profile(rows, {"place:wd:Q84"}, "London")
    assert profile["reference_ranks"] == [2]
    assert profile["exact_recorded_name_or_alias"]
    assert profile["tied_reference_and_other_ids"]
    assert not profile["top_reference_agreement"] and not profile["accepted"]
    assert not candidate_profile(rows[1:], {"place:wd:Q84"}, "London")["accepted"]
    empty = candidate_profile([], set(), ".")
    assert empty["top"] is None and empty["reference_ranks"] == []

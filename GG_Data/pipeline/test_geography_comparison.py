"""The comparison cannot change its population or count broken responses as misses."""

import io
import json
import re
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest

from GG_Data.pipeline import geography_comparison, geography_sample
from GG_Data.pipeline.geography_comparison import (
    candidate_profile,
    query_for,
    query_batches,
    sample_targets,
    validate_response,
)
from GG_Data.pipeline.poc import read_json
from GG_Data.pipeline.rebuild_poc import write


@pytest.mark.parametrize("failure", ["timeout", "remark", "outside"])
def test_osm_batches_resume_without_losing_ids_or_accepting_failed_batches(
    tmp_path, monkeypatch, failure
):
    qids = sorted(f"Q{i}" for i in range(1, 102))
    (tmp_path / "sources").mkdir()
    write(tmp_path / "plan.json", dict(outputs={}))
    write(tmp_path / "queries.json", {})
    write(tmp_path / "sample.json", [dict(wikidata_id=q) for q in qids])
    monkeypatch.setattr(
        geography_sample,
        "tools",
        lambda: SimpleNamespace(OVERPASS={"OpenStreetMap": "https://example.test"}),
    )
    monkeypatch.setitem(
        sys.modules, "GEO_OBJECT_EXTRACTION_POC", SimpleNamespace(USER_AGENT="test")
    )
    calls = []

    def fetch(request, timeout):
        assert timeout == 60
        query = parse_qs(request.data.decode())["data"][0]
        part = re.findall(r"Q\d+", query)
        calls.append(part)
        if len(calls) == 2:
            if failure == "timeout":
                raise TimeoutError("test source timeout")
            if failure == "remark":
                return io.BytesIO(
                    json.dumps(dict(elements=[], remark="timeout")).encode()
                )
            part = ["Q999999"]
        return io.BytesIO(
            json.dumps(
                dict(elements=[dict(tags=dict(wikidata=q)) for q in part])
            ).encode()
        )

    monkeypatch.setattr(geography_comparison.urllib.request, "urlopen", fetch)
    stopped = geography_comparison.retrieve(tmp_path)
    assert stopped["status"] == "STOPPED_FOR_CONSULTATION"
    aggregate = tmp_path / "sources/first_50_openstreetmap.json"
    assert not aggregate.exists()
    assert len(list((tmp_path / "sources").glob("*_batch_*.json"))) == 1
    completed = geography_comparison.retrieve(tmp_path)
    assert completed["status"] == "RETRIEVED"
    assert completed["reused"] == 1
    assert [len(p) for p in calls] == [50, 50, 50, 1]
    saved = read_json(aggregate)
    assert saved["qids"] == qids
    assert [e["tags"]["wikidata"] for e in saved["response"]["elements"]] == qids
    assert len(saved["batches"]) == 3
    calls.clear()
    assert geography_comparison.retrieve(tmp_path)["status"] == "RETRIEVED"
    assert calls == []


def test_batches_keep_all_queries_without_overlap_or_rewriting():
    queries = {f"Q{i}": {"query": str(i)} for i in range(101)}
    batches = query_batches(queries)
    assert [len(b) for b in batches] == [50, 50, 1]
    assert [key for b in batches for key in b] == list(queries)
    assert {key: value for b in batches for key, value in b.items()} == queries
    assert query_batches({}) == []


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

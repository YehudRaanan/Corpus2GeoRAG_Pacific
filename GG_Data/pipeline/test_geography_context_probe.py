"""The context probe must retrieve/cache evidence without assigning identities."""

from types import SimpleNamespace

from GG_Data.pipeline import geography_context_probe as probe
from GG_Data.pipeline.poc import read_json
from GG_Data.pipeline.rebuild_poc import write


def test_probe_creates_cache_then_reuses_exact_request_without_assignments(
    tmp_path, monkeypatch
):
    plan = tmp_path / "plan.json"
    write(
        plan,
        dict(
            queries=[
                dict(
                    place_id="SYN_existing",
                    name="Example",
                    kind="search",
                    params=dict(q="Example, Region"),
                    evidence="Existing mention/page clue only",
                )
            ]
        ),
    )
    calls = []

    def request(url, *, params):
        calls.append((url, params))
        return [dict(name="Example", lat="1", lon="2")]

    monkeypatch.setattr(
        probe,
        "tools",
        lambda: SimpleNamespace(
            NOMINATIM={"OpenStreetMap": "https://example.invalid"},
            request_json=request,
        ),
    )
    monkeypatch.setattr(probe.time, "sleep", lambda _: None)
    output = tmp_path / "new-output"
    assert probe.run(plan, output)["new_requests"] == 1
    assert probe.run(plan, output)["reused_requests"] == 1
    assert len(calls) == 1
    report = read_json(output / "retrieval.json")
    assert report["accepted_assignments"] == 0
    assert report["model_changed"] is False
    assert report["identity_assignments_changed"] is False
    assert report["results"][0]["place_id"] == "SYN_existing"

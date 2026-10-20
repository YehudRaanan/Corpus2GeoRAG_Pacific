"""The new acquisition preflight must stop without altering model inputs."""

import gzip
import json
import sys
import types

import pytest

from GG_Data.pipeline import event_snapshot_discovery as stage
from GG_Data.pipeline.poc import digest


@pytest.mark.parametrize("failure", [False, True])
def test_preflight_reuses_classification_and_never_populates_events(
    tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(stage, "ROOT", tmp_path)
    root = tmp_path / "GG_Data/pipeline/outputs"
    entities, first, hierarchy = [
        root / name for name in ("entities", "first", "hierarchy")
    ]
    for p in (entities, first, hierarchy):
        p.mkdir(parents=True)

    def write(path, value):
        if path.suffix == ".gz":
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(value, f)
        else:
            path.write_text(json.dumps(value), encoding="utf-8")

    reference = tmp_path / "reference.json"
    write(
        reference,
        {
            "project": "geo-test",
            "table_snapshot": {"snapshot_at": "2026-10-18T00:00:00Z"},
        },
    )
    mentions = first / "mentions.json.gz"
    write(mentions, [{"entity_id": "Q1", "raw": {"entity_group": "PER"}}])
    write(first / "manifest.json", {"outputs": {mentions.name: digest(mentions)}})
    write(
        entities / "full_records.json.gz",
        {"Q1": {"entity": {"id": "Q1", "claims": {}}}},
    )
    write(
        entities / "manifest.json",
        {
            "outputs": {
                "full_records.json.gz": digest(entities / "full_records.json.gz")
            },
            "snapshot_at": "2026-10-18T00:00:00Z",
            "inputs": {str(reference): digest(reference)},
        },
    )
    write(
        entities / "verification.json",
        {
            "status": "VERIFIED_ENTITIES_SNAPSHOT_FIRST",
            "manifest_sha256": digest(entities / "manifest.json"),
        },
    )
    write(
        hierarchy / "hierarchy_edges.json",
        {
            "P31": {"Q2": [{"parent": stage.events.EVENT_ROOT, "rank": "normal"}]},
            "P279": {},
        },
    )
    write(hierarchy / "probe.json", {"queries": []})
    write(
        hierarchy / "verification.json",
        {
            "outputs": {
                name: digest(hierarchy / name)
                for name in ("hierarchy_edges.json", "probe.json")
            }
        },
    )
    calls = []

    class Client:
        source = "`approved.snapshot`"
        requests = [{"job_id": "saved-result"}]

        def __init__(self, project, store):
            pass

        def query(self, sql):
            calls.append(sql)
            if failure:
                raise RuntimeError("source timeout")
            return [
                {
                    "incoming_candidate_count": "3",
                    "full_record_bytes": "700",
                    "single_incoming_with_outgoing": "1",
                    "multiple_incoming": "2",
                }
            ]

    monkeypatch.setitem(
        sys.modules,
        "bigquery_direct_wikidata",
        types.SimpleNamespace(BigQueryData=Client),
    )
    before = digest(entities / "full_records.json.gz")
    output = root / "new"
    result = stage.run(entities, mentions, hierarchy, reference, root / "store", output)
    assert len(calls) == 1
    assert digest(entities / "full_records.json.gz") == before
    assert result["cached_hierarchy_positive"] == ["Q2"]
    assert result["event_rows_written"] == 0 and not result["events_complete"]
    assert not (output / "events.json.gz").exists()
    assert (result["status"].startswith("BLOCKED")) == failure
    assert (
        json.loads((output / "report.json").read_text())["status"] == result["status"]
    )

"""Classification must gate full-record acquisition, including its failure path."""

import json

import pytest

from GG_Data.pipeline import event_classification_first as stage
from GG_Data.pipeline.poc import digest


@pytest.mark.parametrize("failure", [False, True])
def test_classification_precedes_retrieval(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(stage, "ROOT", tmp_path)
    root = tmp_path / "GG_Data/pipeline/outputs"
    prior, available, output = [root / name for name in ("prior", "available", "out")]
    prior.mkdir(parents=True)
    available.mkdir()

    def write(path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    hierarchy = prior / "hierarchy_edges.json"
    write(
        hierarchy,
        {
            "P31": {
                "Q1": [{"parent": stage.events.EVENT_ROOT, "rank": "normal"}],
                "Q2": [{"parent": "Q4", "rank": "normal"}],
                "Q3": [{"parent": stage.events.EVENT_ROOT, "rank": "deprecated"}],
            },
            "P279": {"Q4": []},
        },
    )
    reference = prior / "reference_manifest.json"
    write(reference, {"table_snapshot": {"snapshot_at": "approved"}})
    write(
        prior / "classifications.json",
        stage.events.classify_events(stage.read_json(hierarchy)),
    )
    write(
        prior / "report.json",
        {
            "inputs": {str(p): digest(p) for p in (hierarchy, reference)},
            "outputs": {"classifications.json": digest(prior / "classifications.json")},
        },
    )
    write(
        prior / "verification.json",
        {
            "status": "VERIFIED_MEASUREMENT_ONLY_DOWNLOAD_PENDING_CONSULTATION",
            "report_sha256": digest(prior / "report.json"),
        },
    )
    envelope = {"requested_qid": "Q1", "entity": {"id": "Q1", "claims": {}}}
    write(available / "Q1.json", envelope["entity"])
    write(available / "report.json", {"records": [{"qid": "Q1", "source": {}}]})
    write(
        available / "verification.json",
        {"outputs": {p.name: digest(p) for p in available.iterdir()}},
    )
    before = digest(prior / "report.json")
    calls = []

    def acquire(qids, store, reference, *, available_records):
        calls.append(qids)
        decision = stage.read_json(output / "report.json")
        assert decision["status"] == "CLASSIFIED_BEFORE_FULL_RECORD_ACQUISITION"
        assert decision["full_record_qids_requested"] == ["Q1"]
        assert set(available_records) == {"Q1"}
        if failure:
            raise RuntimeError("source failure")
        return {"Q1": envelope}, {"Q1": {"provider": "BIGQUERY"}}

    monkeypatch.setattr(stage.entities, "acquire_missing", acquire)
    result = stage.run(prior, available, root / "store", output)
    assert calls == [{"Q1"}]
    assert digest(prior / "report.json") == before
    assert result["status"].startswith("BLOCKED") == failure
    assert (output / "full_records.json.gz").exists() != failure
    assert result["event_rows_written"] == 0 and not result["events_complete"]

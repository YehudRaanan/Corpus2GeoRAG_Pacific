"""Current class positives must intersect both original candidate inventories."""

import gzip
import json
import re

import pytest

from GG_Data.pipeline import event_instance_candidates as stage
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException


@pytest.mark.parametrize("failure", [False, True])
def test_instance_intersection_and_source_stop(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(stage, "ROOT", tmp_path)
    root = tmp_path / "GG_Data/pipeline/outputs"
    root.mkdir(parents=True)
    catalog, candidates, measurement = [
        root / name for name in ("classes", "ids", "measure")
    ]
    for path in (catalog, candidates, measurement):
        path.mkdir()

    def write(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    # Reconstruct outgoing-only candidates from real native-record links.
    records = root / "full_records.json.gz"
    with gzip.open(records, "wt", encoding="utf-8") as f:
        json.dump(
            {
                "Q1": {
                    "entity": {
                        "id": "Q1",
                        "claims": {
                            "P17": [
                                {
                                    "id": "Q1$11111111-1111-1111-1111-111111111111",
                                    "rank": "normal",
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "property": "P17",
                                        "datatype": "wikibase-item",
                                        "datavalue": {
                                            "type": "wikibase-entityid",
                                            "value": {
                                                "entity-type": "item",
                                                "numeric-id": 3,
                                                "id": "Q3",
                                            },
                                        },
                                    },
                                }
                            ]
                        },
                    }
                }
            },
            f,
        )
    write(
        measurement / "report.json",
        {"inputs": {str(records): digest(records)}, "outgoing_reference_qids": 1},
    )
    with gzip.open(candidates / "candidate_ids.json.gz", "wt", encoding="utf-8") as f:
        json.dump(["Q2", "Q4"], f)
    write(
        candidates / "report.json",
        {
            "candidate_count": 2,
            "outputs": {
                "candidate_ids.json.gz": digest(candidates / "candidate_ids.json.gz")
            },
            "inputs": {
                str(measurement / "report.json"): digest(measurement / "report.json")
            },
        },
    )
    write(
        candidates / "verification.json",
        {
            "status": "VERIFIED_SNAPSHOT_CANDIDATE_IDS_ONLY",
            "report_sha256": digest(candidates / "report.json"),
        },
    )
    write(
        catalog / "catalog.json",
        {"classes": [stage.events.EVENT_ROOT], "completed": [stage.events.EVENT_ROOT]},
    )
    write(
        catalog / "report.json",
        {
            "status": "CURRENT_EVENT_CLASS_CATALOG_COMPLETE_FOR_QUERY_GRAPHS",
            "outputs": {"catalog.json": digest(catalog / "catalog.json")},
            "class_count": 1,
            "queries": [],
        },
    )
    calls = []

    def cached(store, url, params):
        assert "ps:P31" in params["query"]
        assert re.findall(r"wd:(Q\d+)", params["query"]) == [stage.events.EVENT_ROOT]
        calls.append(url)
        if failure and url == stage.events.SCHOLARLY_QUERY_URL:
            raise SourceException("timeout")
        uri = "http://www.wikidata.org/entity/"
        rows = []
        # Q3 is outgoing-only, Q4 is deprecated, Q5 is outside our population.
        for qid, rank in (
            ("Q2", "Normal"),
            ("Q3", "Preferred"),
            ("Q4", "Deprecated"),
            ("Q5", "Normal"),
        ):
            row = dict(
                subject=uri + qid,
                parent=uri + stage.events.EVENT_ROOT,
                property=uri + "P31",
                statement=uri + f"statement/{qid}-11111111-1111-1111-1111-111111111111",
                rank=f"http://wikiba.se/ontology#{rank}Rank",
            )
            rows.append({k: {"value": v} for k, v in row.items()})
        return {"results": {"bindings": rows}}, {"request": {"url": url}}

    monkeypatch.setattr(stage.events, "cached_json", cached)
    result = stage.run(catalog, candidates, measurement, root / "store", root / "new")
    assert read_json(root / "new/positive_qids.json") == ["Q2", "Q3"]
    assert result["candidate_universe_count"] == 3
    assert len(calls) == 2
    assert result["classification_complete"] is (not failure)
    assert result["completed_classes"] == (0 if failure else 1)
    assert result["status"].startswith("BLOCKED") == failure
    assert result["event_rows_written"] == 0 and not result["events_complete"]

    # An incomplete catalog must fail before any new network request.
    report = read_json(catalog / "report.json")
    report["status"] = "RETRIEVING_CURRENT_EVENT_CLASSES"
    write(catalog / "report.json", report)
    with pytest.raises(ValueError, match="incomplete"):
        stage.run(catalog, candidates, measurement, root / "store", root / "other")
    assert len(calls) == 2

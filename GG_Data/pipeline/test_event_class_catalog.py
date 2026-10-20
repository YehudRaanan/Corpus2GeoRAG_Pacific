"""Catalog closure must cross query graphs and stop on source failure."""

import json
import re

import pytest

from GG_Data.pipeline import event_class_catalog as stage
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException


@pytest.mark.parametrize("failure", [False, True])
def test_catalog_crosses_graphs_without_deprecated_expansion(
    tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(stage, "ROOT", tmp_path)
    root = tmp_path / "GG_Data/pipeline/outputs"
    prior, output = root / "prior", root / "new"
    prior.mkdir(parents=True)
    (prior / "report.json").write_text(json.dumps({"outputs": {}}))
    (prior / "verification.json").write_text(
        json.dumps(
            dict(
                status="VERIFIED_CLASSIFICATION_FIRST_BOUNDED_TEST",
                report_sha256=digest(prior / "report.json"),
            )
        )
    )
    calls = []

    def binding(subject, parent, rank):
        uri = "http://www.wikidata.org/entity/"
        values = dict(
            subject=uri + subject,
            parent=uri + parent,
            property=uri + "P279",
            statement=uri + f"statement/{subject}-11111111-1111-1111-1111-111111111111",
            rank=f"http://wikiba.se/ontology#{rank}Rank",
        )
        return {k: {"value": v} for k, v in values.items()}

    def cached(store, url, params):
        query = params["query"]
        batch = re.findall(r"wd:(Q\d+)", query)
        calls.append((url, batch))
        if failure and url == stage.events.SCHOLARLY_QUERY_URL:
            raise SourceException("source timeout")
        rows = []
        if url == stage.events.QUERY_URL and stage.events.EVENT_ROOT in batch:
            rows = [
                binding("Q2", stage.events.EVENT_ROOT, "Normal"),
                binding("Q9", stage.events.EVENT_ROOT, "Deprecated"),
            ]
        if url == stage.events.SCHOLARLY_QUERY_URL and "Q2" in batch:
            rows = [binding("Q3", "Q2", "Preferred")]
        return {"results": {"bindings": rows}}, {"request": {"url": url}}

    monkeypatch.setattr(stage.events, "cached_json", cached)
    result = stage.run(prior, root / "store", output)
    catalog = read_json(output / "catalog.json")
    assert result["status"].startswith("BLOCKED") == failure
    assert "Q9" not in catalog["classes"]
    assert any(e["rank"] == "deprecated" for e in catalog["edges"])
    assert not result["events_complete"] and result["event_rows_written"] == 0
    if failure:
        assert len(calls) == 2 and catalog["completed"] == []
    else:
        assert set(catalog["classes"]) == {stage.events.EVENT_ROOT, "Q2", "Q3"}
        assert catalog["classes"] == catalog["completed"]
        assert len(calls) == 6

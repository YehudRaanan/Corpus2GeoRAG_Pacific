"""Offline checks for the BigQuery reference path, not a new matching method."""

import json

import pytest

from bigquery_direct_wikidata import BigQueryData, project_entity
from bilingual_page_pilot import read


@pytest.fixture(autouse=True)
def offline_cli(monkeypatch):
    monkeypatch.setattr("bigquery_direct_wikidata.shutil.which", lambda _: "bq.cmd")


def test_bigquery_projection_preserves_names_and_filters_deprecated_claims():
    def claim(qid, rank="normal"):
        return json.dumps(
            {"rank": rank, "mainsnak": {"datavalue": {"value": {"id": qid}}}}
        )

    raw = {
        "id": "Q1",
        "labels": [
            {"language": "en", "value": "Person"},
            {"language": "ja", "value": "人物"},
        ],
        "aliases": [{"language": "en", "value": "Alias"}],
        "sitelinks": [{"site": "enwiki", "title": "Person article"}],
        "p31": [claim("Q5"), claim("Q43229", "deprecated")],
        "p279": [claim("Q2"), json.dumps({"mainsnak": {"snaktype": "somevalue"}})],
        "revision": "123",
    }
    result = project_entity(raw)
    assert result["direct_types"] == ["Q5"]
    assert result["parents"] == ["Q2"]
    assert result["aliases"] == ["Alias", "Person", "Person article", "人物"]
    assert result["revision"] == 123


@pytest.mark.parametrize("destination_rows", [1, 2])
def test_bigquery_query_reuses_saved_rows_and_checks_complete_result(
    tmp_path, monkeypatch, destination_rows
):
    calls = []

    def cli(self, args, sql=None):
        calls.append(args)
        if args == ["show", "bigquery-public-data:wikipedia.wikidata"]:
            return json.dumps(
                {
                    "id": "bigquery-public-data:wikipedia.wikidata",
                    "lastModifiedTime": "123",
                }
            )
        if "--dry_run" in args:
            return "Query validated"
        if args[0] == "query":
            return json.dumps([{"qid": "Q5"}])
        if "--job=true" in args:
            return json.dumps(
                {
                    "configuration": {
                        "query": {
                            "destinationTable": {
                                "projectId": "p",
                                "datasetId": "d",
                                "tableId": "t",
                            }
                        }
                    },
                    "statistics": {"query": {"totalBytesBilled": "100"}},
                }
            )
        return json.dumps({"numRows": str(destination_rows)})

    monkeypatch.setattr(BigQueryData, "cli", cli)
    api = BigQueryData("handover-480513", tmp_path)
    if destination_rows != 1:
        with pytest.raises(ValueError, match="truncated"):
            api.query("SELECT 'Q5' AS qid")
        assert not list(tmp_path.glob("*.json.gz"))
        return
    assert api.query("SELECT 'Q5' AS qid") == [{"qid": "Q5"}]
    previous_calls = len(calls)
    fresh = BigQueryData("handover-480513", tmp_path)
    assert fresh.query("SELECT 'Q5' AS qid") == [{"qid": "Q5"}]
    assert len(calls) == previous_calls
    assert fresh.requests[0]["statistics"]["query"]["totalBytesBilled"] == "100"


def test_missing_bigquery_ids_are_explicit_and_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(
        BigQueryData,
        "cli",
        lambda *args: json.dumps(
            {"id": "bigquery-public-data:wikipedia.wikidata", "lastModifiedTime": "123"}
        ),
    )
    monkeypatch.setattr(BigQueryData, "query", lambda *args: [])
    api = BigQueryData("handover-480513", tmp_path)
    api.entities_for({"Q999"})
    assert api.entities["Q999"]["missing"] is True
    assert api.entities["Q999"]["direct_types"] == []
    assert read(api.metadata_path)["Q999"] == api.entities["Q999"]


def test_cli_load_uses_project_colon_dataset_table(tmp_path, monkeypatch):
    calls = []

    def cli(self, args, sql=None):
        calls.append(args)
        return json.dumps(
            {"id": "bigquery-public-data:wikipedia.wikidata", "lastModifiedTime": "123"}
        )

    monkeypatch.setattr(BigQueryData, "cli", cli)
    api = BigQueryData("handover-480513", tmp_path)
    table = api.upload_values(["日本", "O'Brien"], "name")
    load = next(args for args in calls if args[0] == "load")
    assert load[3] == table.replace(".", ":", 1)
    assert table.startswith("handover-480513.geoai_resolution_20261018.")
    other = BigQueryData("geo-hagai-ndvi", tmp_path)
    previous_calls = len(calls)
    assert other.upload_values(["日本", "O'Brien"], "name") == table
    assert len(calls) == previous_calls


def test_incomplete_page_snapshot_stops_before_any_network(tmp_path, monkeypatch):
    import bigquery_direct_wikidata as runner
    from bilingual_page_pilot import digest
    from full_direct_wikidata import save

    source = tmp_path / "input"
    source.write_bytes(b"pinned input")
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    save(
        snapshot / "page_snapshot_manifest.json",
        {"input_sha256": digest(source), "files": {}},
    )
    monkeypatch.setattr(runner, "INPUT", source)
    monkeypatch.setattr(runner, "input_rows", lambda: [{"raw": {"Source": "Example"}}])
    monkeypatch.setattr(
        runner, "BigQueryData", lambda *a: pytest.fail("Unexpected network client")
    )
    with pytest.raises(ValueError, match="every Daniel source"):
        runner.execute(
            "geo-hagai-ndvi",
            tmp_path / "store",
            tmp_path / "output",
            page_snapshot=snapshot,
        )

"""Offline enrichment stages; all acquisition evidence is fixture data."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from GG_Data.pipeline import post_qid_enrich as api


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def claim(qid, prop, target, sid):
    return {
        "id": qid + "$" + sid,
        "rank": "normal",
        "mainsnak": {
            "property": prop,
            "snaktype": "value",
            "datatype": "wikibase-item",
            "datavalue": {
                "value": {
                    "entity-type": "item",
                    "id": target,
                    "numeric-id": int(target[1:]),
                }
            },
        },
    }


def hierarchy(tmp_path):
    directory = tmp_path / "hierarchy"
    types = directory / "parameters" / "event_types.csv"
    types.parent.mkdir(parents=True)
    types.write_text("subtype_qid\nQ1190554\n")
    write(
        directory / "recognition_approval.json",
        {
            "status": "RECOGNITION_RULE_ACCEPTED",
            "root_qid": "Q1190554",
            "parameter_hashes": {"event_types.csv": sha(types)},
        },
    )
    return directory


def test_public_discovery_uses_raw_main_statements_all_ranks_without_retention_filters():
    sql = api.sparql_incoming_query({"Q1", "Q2"})
    assert "VALUES ?corpus { wd:Q1 wd:Q2 }" in sql
    assert "wikibase:claim ?claim" in sql
    assert "wikibase:statementProperty ?valueProperty" in sql
    assert "?statement ?valueProperty ?corpus" in sql
    assert "LIMIT" not in sql
    assert "PreferredRank" not in sql
    assert "P279" not in sql
    assert "P279" in api.sparql_incoming_query({"Q1"}, live_hierarchy_prefilter=True)
    with pytest.raises(ValueError, match="corpus QIDs"):
        api.sparql_incoming_query({"not a QID"})


def test_public_discovery_bindings_are_scoped_and_keep_incoming_pairs():
    data = {
        "results": {
            "bindings": [
                {
                    "event": {
                        "type": "uri",
                        "value": "http://www.wikidata.org/entity/Q3",
                    },
                    "corpus": {
                        "type": "uri",
                        "value": "http://www.wikidata.org/entity/Q1",
                    },
                }
            ]
        }
    }
    assert api.sparql_incoming_pairs(data, {"Q1"}) == [
        {"event_qid": "Q3", "daniel_qid": "Q1"}
    ]
    with pytest.raises(ValueError, match="outside corpus"):
        api.sparql_incoming_pairs(data, {"Q2"})


def consolidation_inputs(tmp_path):
    one = {"requested_qid": "Q1", "entity": {"id": "Q1", "claims": {}, "lastrevid": 1}}
    two = {"requested_qid": "Q2", "entity": {"id": "Q2", "claims": {}, "lastrevid": 2}}
    old_raw = write(tmp_path / "old_record.json", one)
    live_raw = write(
        tmp_path / "live_response.json", {"entities": {"Q2": two["entity"]}}
    )
    old_source = {
        "file": str(old_raw),
        "sha256": sha(old_raw),
        "record_id": "Q1",
        "snapshot_at": "2026-10-18",
    }
    live_source = {
        "provider": "WIKIDATA_API",
        "file": str(live_raw),
        "sha256": sha(live_raw),
        "record_id": "Q2",
        "retrieved_at": "2026-10-29T00:00:00Z",
        "snapshot_at": None,
    }
    inventory = write(
        tmp_path / "reuse.json",
        {
            "records": {"Q1": one},
            "sources": {"Q1": old_source},
            "missing": ["Q2"],
            "counts": {"required": 2, "reused": 1, "missing": 1},
        },
    )
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    with gzip.open(api_dir / "full_records.json.gz", "wt", encoding="utf-8") as stream:
        json.dump({"Q2": two}, stream)
    write(api_dir / "sources.json", {"Q2": live_source})
    write(
        api_dir / "receipt.json",
        {
            "status": "REQUIRED_NATIVE_RECORDS_AVAILABLE",
            "requested_ids": ["Q2"],
            "missing": [],
            "failures": [],
            "counts": {"required": 1, "acquired": 1, "missing": 0},
            "outputs": {
                name: sha(api_dir / name)
                for name in ("full_records.json.gz", "sources.json")
            },
        },
    )
    return inventory, api_dir, one, two


def test_consolidation_preserves_whole_versions_and_exact_source_provenance(tmp_path):
    inventory, api_dir, one, two = consolidation_inputs(tmp_path)
    out = tmp_path / "native_complete"
    receipt = api.consolidate_native(inventory, api_dir, {"Q1", "Q2"}, out)
    assert receipt["counts"] == {
        "required": 2,
        "reused": 1,
        "acquired": 1,
        "missing": 0,
    }
    with gzip.open(out / "full_records.json.gz", "rt", encoding="utf-8") as stream:
        assert json.load(stream) == {"Q1": one, "Q2": two}
    assert json.loads((out / "sources.json").read_text())["Q2"]["snapshot_at"] is None
    assert receipt["event_discovery_completeness"] == "NOT_ESTABLISHED"
    assert (out / "manifest.json").is_file()


def test_consolidation_rejects_changed_output_wrong_scope_and_source_mutation(tmp_path):
    inventory, api_dir, _, _ = consolidation_inputs(tmp_path)
    with pytest.raises(ValueError, match="scope"):
        api.consolidate_native(
            inventory, api_dir, {"Q1", "Q2", "Q3"}, tmp_path / "wrong"
        )
    source = json.loads((api_dir / "sources.json").read_text())["Q2"]
    Path(source["file"]).write_text("changed")
    with pytest.raises(ValueError, match="hash differs"):
        api.consolidate_native(inventory, api_dir, {"Q1", "Q2"}, tmp_path / "changed")


def test_public_apply_requires_all_outgoing_targets_and_pins_evidence(
    tmp_path, monkeypatch
):
    corpus = {
        q: {
            "requested_qid": q,
            "entity": {"id": q, "claims": {"P17": [claim(q, "P17", "Q3", "out")]}},
        }
        for q in ("Q1", "Q2")
    }
    candidate = {
        "Q3": {
            "requested_qid": "Q3",
            "entity": {
                "id": "Q3",
                "claims": {"P31": [claim("Q3", "P31", "Q1190554", "type")]},
            },
        }
    }
    native, bundle, core = (tmp_path / n for n in ("native", "bundle", "core"))

    def consolidated_fixture(directory, records):
        raw = write(tmp_path / (directory.name + "_raw.json"), records)
        api._write_stage(
            directory,
            {
                "full_records.json.gz": records,
                "sources.json": {
                    q: {
                        "record_id": q,
                        "snapshot_at": None,
                        "file": str(raw),
                        "sha256": sha(raw),
                    }
                    for q in records
                },
            },
            {
                "required_qids": sorted(records),
                "counts": {"missing": 0},
                "phase": "NATIVE_CONSOLIDATION",
                "inputs": {str(raw): sha(raw)},
                "source_files": {str(raw.resolve()): sha(raw)},
            },
        )

    for directory, records in ((native, corpus), (bundle, candidate)):
        consolidated_fixture(directory, records)
    core.mkdir()
    entities = [dict(entity_id=q, type="MISC") for q in corpus]
    with gzip.open(core / "entities.json.gz", "wt") as f:
        json.dump(entities, f)
    write(
        core / "manifest.json",
        {"scope": "3", "outputs": {"entities.json.gz": sha(core / "entities.json.gz")}},
    )
    h = hierarchy(tmp_path)
    query = tmp_path / "query.rq"
    query.write_text("VALUES ?corpus { wd:Q1 wd:Q2 } HAVING (?event IN (wd:Q3))")
    response = write(
        tmp_path / "response.json",
        {
            "head": {"vars": ["event", "corpus_values", "type_values"]},
            "results": {"bindings": []},
        },
    )
    monkeypatch.setattr(api, "_mapping", lambda *a: ({}, {}))
    kwargs = dict(
        core_dir=core,
        native_dir=native,
        candidate_dir=bundle,
        query=query,
        query_sha256=sha(query),
        response=response,
        response_sha256=sha(response),
        observed_at="2026-10-29T07:00:00Z",
        hierarchy=h,
        approval_sha256=sha(h / "recognition_approval.json"),
        mapping_dir=tmp_path,
        mapping_manifest=query,
        mapping_manifest_sha256=sha(query),
    )
    result = api.apply_public_events(**kwargs, output=tmp_path / "applied")
    assert result["counts"]["events"] == 1  # Outgoing-only Event absent from response.
    assert result["counts"]["stored_directed_rows"] == 4
    assert result["temporal_basis"] == "MIXED_WHOLE_RECORD_VERSIONS_NO_COMMON_SNAPSHOT"
    assert (
        result["event_discovery_completeness"]
        == "SPARQL_OBSERVATION_AND_LOCAL_OUTGOING_UNION_ONLY"
    )
    with pytest.raises(ValueError, match="hash differs"):
        api.apply_public_events(
            **{**kwargs, "response_sha256": "0" * 64}, output=tmp_path / "bad"
        )
    consolidated_fixture(tmp_path / "empty", {})
    with pytest.raises(ValueError, match="Missing full candidate"):
        api.apply_public_events(
            **{**kwargs, "candidate_dir": tmp_path / "empty"},
            output=tmp_path / "missing"
        )

    candidate["Q3"]["entity"]["claims"]["P31"][0]["rank"] = "deprecated"
    rejected = tmp_path / "deprecated"
    consolidated_fixture(rejected, candidate)
    result = api.apply_public_events(
        **{**kwargs, "candidate_dir": rejected, "observed_at": None},
        output=tmp_path / "rechecked"
    )
    assert result["counts"]["events"] == 0
    assert result["sparql_observed_at"] is None


def test_consolidation_rejects_inventory_tamper_and_changed_sql(tmp_path):
    inventory, api_dir, _, _ = consolidation_inputs(tmp_path)
    data = json.loads(inventory.read_text())
    data["records"]["Q1"]["entity"]["claims"] = {
        "P17": [claim("Q1", "P17", "Q2", "invented")]
    }
    write(inventory, data)
    with pytest.raises(ValueError, match="differs from source bytes"):
        api.consolidate_native(inventory, api_dir, {"Q1", "Q2"}, tmp_path / "tampered")
    data["records"]["Q1"]["entity"]["claims"] = {}
    sql = tmp_path / "source.sql"
    sql.write_text("SELECT id,item FROM source")
    data["sources"]["Q1"].update(sql_file=str(sql), sql_sha256=sha(sql))
    write(inventory, data)
    sql.write_text("changed")
    with pytest.raises(ValueError, match="hash differs"):
        api.consolidate_native(
            inventory, api_dir, {"Q1", "Q2"}, tmp_path / "sql_changed"
        )


def test_event_entity_reference_source_uses_actual_provider(monkeypatch):
    record = {"id": "Q3", "claims": {}}
    entity, _ = api._event_tables(
        record, {"provider": "WIKIDATA_API"}, {"linked_corpus_qids": ["Q1", "Q2"]}
    )
    assert entity["reference_source"] == "WIKIDATA_API"
    original = api.event_rows
    calls = []

    def ambiguous(record, source, decision):
        if not calls:
            calls.append(True)
            raise api.SourceException("fixture date ambiguity")
        return original(record, source, decision)

    monkeypatch.setattr(api, "event_rows", ambiguous)
    entity, _ = api._event_tables(
        record, {"provider": "WIKIDATA_API"}, {"linked_corpus_qids": ["Q1", "Q2"]}
    )
    assert entity["reference_source"] == "WIKIDATA_API"


def test_consolidated_boundary_rejects_direct_api_and_changed_inputs(tmp_path):
    inventory, api_dir, _, _ = consolidation_inputs(tmp_path)
    with pytest.raises(ValueError, match="NATIVE_CONSOLIDATION"):
        api._consolidated_stage(api_dir)
    out = tmp_path / "consolidated"
    api.consolidate_native(inventory, api_dir, {"Q1", "Q2"}, out)
    assert api._consolidated_stage(out)["phase"] == "NATIVE_CONSOLIDATION"
    inventory.write_text("changed")
    with pytest.raises(ValueError, match="hash differs"):
        api._consolidated_stage(out)

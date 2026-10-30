"""Offline Event stages, with no acquisition or source changes."""

import gzip
import hashlib
import json

import pytest

from GG_Data.pipeline import post_qid_events as api


def test_discovery_with_no_bindings_returns_no_candidates():
    assert api.sparql_incoming_pairs({"results": {"bindings": []}}, {"Q1"}) == []


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


def test_article_boundary_uses_exact_revision_raw_links_and_keeps_corpus_events(
    tmp_path, monkeypatch
):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import raw_links

    raw = tmp_path / "article.txt"
    raw.write_text("[[Linked event]]", encoding="utf-8")
    core = tmp_path / "core"
    core.mkdir()
    for name, value in {
        "entities.json.gz": [dict(entity_id=q, type="MISC") for q in ("Q1", "Q2")],
        "wiki_pages.json.gz": [
            {
                "wiki_page_id": 10,
                "revision_id": 20,
                "raw_reference": {"wikitext_path": str(raw), "sha256": sha(raw)},
            }
        ],
    }.items():
        with gzip.open(core / name, "wt") as stream:
            json.dump(value, stream)
    write(
        core / "manifest.json",
        {
            "scope": "3",
            "outputs": {
                name: sha(core / name)
                for name in ("entities.json.gz", "wiki_pages.json.gz")
            },
        },
    )
    link = {
        **raw_links(raw.read_text())[0],
        "page_id": 10,
        "revision_id": 20,
        "raw_evidence_path": str(raw),
        "raw_sha256": sha(raw),
        "qid": "Q3",
        "mapping_temporal_basis": "CURRENT_OR_CACHED",
    }
    table = tmp_path / "wiki_link_occurrences.parquet"
    pq.write_table(
        pa.Table.from_pylist([link, {**link, "qid": "Q4", "revision_id": 21}]), table
    )
    summary = write(
        tmp_path / "collection_summary.json", {"outputs": {table.name: sha(table)}}
    )
    records = {
        q: {"requested_qid": q, "entity": {"id": q, "claims": {}}}
        for q in ("Q1", "Q2", "Q3", "Q4")
    }
    for q in ("Q3", "Q4"):
        records[q]["entity"]["claims"] = {
            "P17": [claim(q, "P17", t, t) for t in ("Q1", "Q2")]
        }
    broad = tmp_path / "broad"
    api._write_stage(
        broad,
        {
            "full_records.json.gz": records,
            "sources.json": {q: {"provider": "FIXTURE"} for q in records},
            "events.json.gz": [{"event_id": q} for q in ("Q1", "Q3", "Q4")],
            "event_entities.json.gz": [{"entity_id": q} for q in ("Q1", "Q3", "Q4")],
            "event_decisions.json": [
                {"qid": q, "keep_event": True} for q in ("Q1", "Q3", "Q4")
            ],
        },
        {"scope": "3", "temporal_basis": "MIXED", "sparql_observed_at": None},
    )
    monkeypatch.setattr(api, "_mapping", lambda *a: ({}, {}))
    args = (core, broad, table, summary, tmp_path, summary, sha(summary))
    out = tmp_path / "restricted"
    result = api.restrict_events_to_articles(*args, out)
    assert result["counts"]["events"] == 2
    assert {e["event_id"] for e in api.read_json(out / "events.json.gz")} == {
        "Q1",
        "Q3",
    }
    assert result["counts"]["added_events"] == 1
    assert result["counts"]["stored_directed_rows"] == 4
    decisions = {d["qid"]: d for d in api.read_json(out / "event_decisions.json")}
    assert (
        decisions["Q4"]["article_presence_reason"] == "NO_DIRECT_LINK_IN_USED_REVISIONS"
    )
    link["raw_start"] += 1
    pq.write_table(pa.Table.from_pylist([link]), table)
    write(summary, {"outputs": {table.name: sha(table)}})
    with pytest.raises(ValueError, match="raw link"):
        api.restrict_events_to_articles(*args, tmp_path / "bad")


def shared_article_fixture(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.filter_qid_inventory import (
        POLICY_VERSION,
    )
    from GG_Data.pipeline.test_revised_enrichment import article_fixture

    core, table, collection = article_fixture(tmp_path)
    rows = [
        dict(
            page_id=1,
            revision_id=20,
            qid=q,
            qid_source_status=status,
            qid_filter_policy_version=POLICY_VERSION,
            type_categories=["DATE"],
            type_unknown=False,
            link_origin=[origin],
        )
        for q, status, origin in [
            ("Q3", "KEEP", "RAW_DIRECT_LINK"),
            ("Q7", "REVIEW_KEEP", "RAW_SHIP_TEMPLATE"),
            ("Q8", "UNKNOWN_KEEP", "RAW_DIRECT_LINK"),
            ("Q9", "KEEP", "PAGE_OWN_QID"),
        ]
    ]
    rows.append(dict(rows[0], qid="Q99", revision_id=21))
    inventory = tmp_path / "shared_inventory.parquet"
    pq.write_table(pa.Table.from_pylist(rows), inventory)
    manifest = api.read_json(core / "manifest.json")
    manifest.update(
        used_revisions=[[p, 20] for p in (1, 2, 3)],
        scoped_qid_inventory=dict(
            path=str(inventory.resolve()),
            sha256=sha(inventory),
            policy_version=POLICY_VERSION,
        ),
    )
    write(core / "manifest.json", manifest)
    return core, table, collection, inventory


def test_shared_inventory_drives_event_presence_without_daniel_type_veto(tmp_path):
    core, table, collection, inventory = shared_article_fixture(tmp_path)
    _, _, presence, inputs = api._article_evidence(core, table, collection)
    assert {r["qid"] for r in presence if r["retained_content_link"]} == {
        "Q3",
        "Q7",
        "Q8",
        "Q9",
    }
    assert inputs[str(inventory.resolve())] == sha(inventory)
    assert {r["qid_source_status"] for r in presence} == {
        "KEEP",
        "REVIEW_KEEP",
        "UNKNOWN_KEEP",
    }


@pytest.mark.parametrize(
    "corruption",
    ["hash", "policy", "row_policy", "excluded", "types", "scope", "null_binding"],
)
def test_shared_event_inventory_rejects_changed_or_invalid_scope(tmp_path, corruption):
    import pyarrow as pa
    import pyarrow.parquet as pq

    core, table, collection, inventory = shared_article_fixture(tmp_path)
    manifest = api.read_json(core / "manifest.json")
    if corruption == "null_binding":
        manifest["scoped_qid_inventory"] = None
    elif corruption == "hash":
        manifest["scoped_qid_inventory"]["sha256"] = "0" * 64
    elif corruption == "policy":
        manifest["scoped_qid_inventory"]["policy_version"] = "unknown-policy"
    elif corruption == "scope":
        manifest["used_revisions"][0][1] = 999
    else:
        rows = pq.read_table(inventory).to_pylist()
        key, value = {
            "row_policy": ("qid_filter_policy_version", "unknown-policy"),
            "excluded": ("qid_source_status", "EXCLUDE"),
            "types": ("type_unknown", None),
        }[corruption]
        rows[0][key] = value
        pq.write_table(pa.Table.from_pylist(rows), inventory)
        manifest["scoped_qid_inventory"]["sha256"] = sha(inventory)
    write(core / "manifest.json", manifest)
    with pytest.raises(ValueError, match="hash differs|shared|scoped|revision"):
        api._article_evidence(core, table, collection)


def test_cached_event_receipt_binds_shared_inventory_and_keeps_review_gaps(
    tmp_path, monkeypatch
):
    core, table, collection, inventory = shared_article_fixture(tmp_path)
    native = tmp_path / "native"
    raw = write(tmp_path / "native_raw.json", {})
    api._write_stage(
        native,
        {"full_records.json.gz": {}, "sources.json": {}},
        dict(
            phase="NATIVE_CONSOLIDATION",
            inputs={str(raw): sha(raw)},
            source_files={str(raw.resolve()): sha(raw)},
        ),
    )
    h = hierarchy(tmp_path)
    monkeypatch.setattr(api, "_mapping", lambda *args: ({}, {}))
    receipt = api.apply_cached_events(
        core_dir=core,
        native_dir=native,
        link_table=table,
        collection_manifest=collection,
        hierarchy=h,
        approval_sha256=sha(h / "recognition_approval.json"),
        mapping_dir=tmp_path,
        mapping_manifest=collection,
        mapping_manifest_sha256=sha(collection),
        output=tmp_path / "events",
    )
    assert receipt["inputs"][str(inventory.resolve())] == sha(inventory)
    assert receipt["missing_article_qids"] == ["Q3", "Q7", "Q8", "Q9"]
    assert receipt["used_revisions"] == [[1, 20], [2, 20], [3, 20]]


def test_restricted_event_receipt_binds_shared_inventory_and_exact_revisions(
    tmp_path, monkeypatch
):
    core, table, collection, inventory = shared_article_fixture(tmp_path)
    qids = ("Q1", "Q2", "Q7", "Q99")
    broad = tmp_path / "broad"
    api._write_stage(
        broad,
        {
            "full_records.json.gz": {
                q: dict(requested_qid=q, entity=dict(id=q, claims={})) for q in qids
            },
            "sources.json": {q: {"provider": "FIXTURE"} for q in qids},
            "events.json.gz": [{"event_id": q} for q in qids],
            "event_entities.json.gz": [{"entity_id": q} for q in qids],
            "event_decisions.json": [{"qid": q, "keep_event": True} for q in qids],
        },
        dict(scope="3", temporal_basis="MIXED"),
    )
    monkeypatch.setattr(api, "_mapping", lambda *args: ({}, {}))
    receipt = api.restrict_events_to_articles(
        core,
        broad,
        table,
        collection,
        tmp_path,
        collection,
        sha(collection),
        tmp_path / "events",
    )
    assert receipt["inputs"][str(inventory.resolve())] == sha(inventory)
    assert receipt["used_revisions"] == [[1, 20], [2, 20], [3, 20]]
    assert {
        r["event_id"] for r in api.read_json(tmp_path / "events/events.json.gz")
    } == {"Q1", "Q2", "Q7"}

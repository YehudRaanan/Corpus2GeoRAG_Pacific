"""Keep exact LOC keys and require the core delivery before geography work."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.pipeline import simplified_agent as source
from GG_Data.pipeline.poc import digest, read_json


def test_population_worker_stops_failed_source_and_does_not_repeat_it(
    tmp_path, monkeypatch
):
    from GG_Data.pipeline import geography_comparison
    from GG_Data.pipeline import simplified_geography as geography

    base = tmp_path / "geo"
    (base / "geography_inputs").mkdir(parents=True)
    source.write_object(
        base / "geography_inputs/report.json", dict(failed_input_targets=0, outputs={})
    )
    source.write_object(base / "geography_inputs/targets.json", [dict(place_id="A")])
    calls = []

    def prepare(base, start, size):
        folder = base / "batches" / f"{start:06d}"
        (folder / "retrieval").mkdir(parents=True)
        return folder

    def retrieve(path):
        calls.append(path)
        return dict(
            status="STOPPED_FOR_CONSULTATION", error_type="HTTPError", error="429"
        )

    monkeypatch.setattr(geography, "prepare_batch", prepare)
    monkeypatch.setattr(geography_comparison, "retrieve", retrieve)
    with pytest.raises(RuntimeError, match="429"):
        geography.run_population(base, tmp_path / "metadata.json", batch_size=1)
    stopped = read_json(base / "progress.json")
    assert stopped["status"] == "STOPPED_REQUIRES_REVIEW"
    assert stopped["completed_targets"] == 0
    with pytest.raises(ValueError, match="Incomplete batch"):
        geography.run_population(base, tmp_path / "metadata.json", batch_size=1)
    assert len(calls) == 1


def test_geography_aggregation_requires_every_target_and_verified_native_shapes(
    tmp_path,
):
    from GG_Data.pipeline.simplified_geography import aggregate_geography

    base = tmp_path / "geo"
    (base / "geography_inputs").mkdir(parents=True)
    source.write_object(base / "geography_inputs/report.json", dict(all_loc_targets=3))
    source.write_object(
        base / "geography_inputs/targets.json",
        [dict(place_id="island", name="Island"), dict(place_id="empty", name="Empty")],
    )
    source.write_object(
        base / "geography_inputs/failed_inputs.json",
        [
            dict(
                place_id="invalid",
                name="Invalid",
                status="FAILED_INPUT_NO_VALID_MENTION_SPAN",
            )
        ],
    )
    with pytest.raises(ValueError, match="Incomplete"):
        aggregate_geography(base, tmp_path / "missing.json.gz")
    folder = base / "batches/000000/ranking"
    folder.mkdir(parents=True)
    polygon = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    chosen = dict(
        geometry=polygon,
        source="OpenStreetMap",
        source_id="R1",
        total=72,
        receipt="saved.json",
        uncertainty_flags=["SOURCE_DATE_UNKNOWN"],
    )
    source.write_object(
        folder / "audit.json",
        dict(
            results=[
                dict(
                    input=dict(place_id="island", name="Island"),
                    proposed=chosen,
                    ranking=[chosen],
                ),
                dict(
                    input=dict(place_id="empty", name="Empty"),
                    proposed=None,
                    ranking=[],
                ),
            ]
        ),
    )
    source.write_object(
        folder / "verification.json",
        dict(
            status="VERIFIED_RANKING_PROPOSALS",
            inputs=2,
            outputs={"audit.json": digest(folder / "audit.json")},
        ),
    )
    output = tmp_path / "geography.json.gz"
    result = aggregate_geography(base, output)
    rows = {r["place_id"]: r for r in read_json(output)}
    assert result["processed"] == 3 and result["resolved"] == 1
    assert rows["island"]["geometry"] == polygon
    assert rows["island"]["selection"]["uncertainty_flags"] == ["SOURCE_DATE_UNKNOWN"]
    assert rows["empty"]["status"] == "UNRESOLVED_NO_ELIGIBLE_SOURCE_GEOMETRY"
    assert rows["invalid"]["geometry"] is None
    assert not any("wikidata_id" in r for r in rows.values())
    with pytest.raises(FileExistsError):
        aggregate_geography(base, output)
    (folder / "audit.json").write_text("{}")
    with pytest.raises(ValueError, match="Changed"):
        aggregate_geography(base, tmp_path / "changed.json.gz")


def test_geography_prepares_all_exact_loc_keys_without_identity_assignments(tmp_path):
    from GG_Data.pipeline.simplified_geography import prepare_geography

    rows = [
        dict(
            word=name,
            entity_group=kind,
            Source="Q1",
            Text=text,
            start=start,
            end=end,
            Index=i,
            score=0.9,
            subtype=kind,
        )
        for i, (name, kind, text, start, end) in enumerate(
            [
                ("Paris", "LOC", "bad span", 0, 5),
                ("Paris", "LOC", "Paris in France", 0, 5),
                ("paris", "LOC", "paris", 0, 5),
                ("Wrong", "LOC", "other", 0, 5),
                ("Paris", "PER", "Paris", 0, 5),
                ("1941", "DATE", "1941", 0, 4),
            ]
        )
    ]
    parquet = tmp_path / "input.parquet"
    pq.write_table(pa.Table.from_pylist(rows), parquet)
    model = tmp_path / "model"
    source.prepare(parquet, model, expected_sha256=digest(parquet))
    release = tmp_path / "core"
    release.mkdir()
    source.write_object(release / "manifest.json", dict(stage="INCOMPLETE"))
    output = tmp_path / "geography"
    with pytest.raises(ValueError, match="core"):
        prepare_geography(model, release, output)
    assert not output.exists()
    (release / "model").mkdir()
    (release / "model/manifest.json").write_bytes(
        (model / "manifest.json").read_bytes()
    )
    # Replace this test-only manifest; production inputs are never rewritten.
    (release / "manifest.json").write_text(
        json.dumps(
            dict(
                stage="CORE_RELEASE_GEOGRAPHY_PENDING",
                outputs={"model/manifest.json": digest(model / "manifest.json")},
            )
        )
    )
    result = prepare_geography(model, release, output)
    assert result["all_loc_targets"] == 3
    assert result["ready_targets"] == 2 and result["failed_input_targets"] == 1
    targets = read_json(output / "geography_inputs/targets.json")
    assert {p["name"] for p in targets} == {"Paris", "paris"}
    assert all(p["wikidata_id"] is None for p in targets)
    assert all(p["selection_date"] == "1941-12-07" for p in targets)
    paris = next(p for p in targets if p["name"] == "Paris")
    assert paris["source_context"][0]["mention_id"] == "mention:1"
    assert result["new_source_requests"] == 0
    from GG_Data.pipeline.simplified_geography import prepare_batch

    batch = prepare_batch(output, 0, 1)
    assert read_json(batch / "manifest.json")["size"] == 1
    evidence = read_json(batch / "retrieval/evidence.json")
    assert len(evidence) == 1
    assert next(iter(evidence.values()))["same_page_location_names"] == [
        "Paris",
        "Wrong",
        "paris",
    ]
    # Run the real legacy ranker with exact cached zero-result responses.
    # Unknown locations must complete without inventing a shape or network call.
    from GG_Data.pipeline import geography_ranking_sample as ranking
    from GG_Data.pipeline.geography_sample import tools

    comparison = batch / "retrieval"
    place = read_json(comparison / "sample.json")[0]
    for arm in ["native", "existing_dated"]:
        source.write_object(
            comparison / f"sources/whg_{arm}.json",
            dict(response={place["place_id"]: {"result": []}}),
        )
    for service in ["openstreetmap", "openhistoricalmap"]:
        source.write_object(
            comparison / f"sources/first_50_{service}.json",
            dict(response={"elements": []}),
        )
    source.write_object(comparison / "progress.json", dict(status="RETRIEVED"))
    import gzip

    with gzip.open(
        comparison / "candidate_records.json.gz", "xt", encoding="utf-8"
    ) as stream:
        stream.write("{}")
    source.write_object(
        comparison / "candidate_records_report.json",
        dict(
            outputs={
                "candidate_records.json.gz": digest(
                    comparison / "candidate_records.json.gz"
                )
            }
        ),
    )
    cache = tmp_path / "source_cache"
    (cache / "sources").mkdir(parents=True)
    source.write_object(
        cache / "sources/search.json",
        dict(
            url=tools().NOMINATIM["OpenStreetMap"] + "/search",
            params=dict(
                format="jsonv2",
                polygon_geojson="1",
                extratags="1",
                namedetails="1",
                addressdetails="1",
                q=place["name"],
                limit="10",
            ),
            response=[],
        ),
    )
    result = ranking.run(
        tmp_path / "ranking", cache, comparison, base_dir=output, cache_only=True
    )
    assert result["inputs"] == result["no_geometry_proposal"] == 1
    assert result["new_requests"] == result["geometry_proposals"] == 0
    with pytest.raises(FileExistsError):
        prepare_geography(model, release, output)


def test_nominatim_pacing_persists_across_batches(tmp_path):
    from types import SimpleNamespace

    from GG_Data.pipeline.simplified_geography import slow_nominatim

    elapsed = [100.0]
    calls = []

    def sleep(seconds):
        elapsed[0] += seconds

    def request(url, **kwargs):
        calls.append(elapsed[0])
        return []

    client = SimpleNamespace(
        NOMINATIM={"OpenStreetMap": "https://geo.test"}, request_json=request
    )
    state = tmp_path / "pacing.json"
    for _ in range(2):
        with slow_nominatim(client, state, now=lambda: elapsed[0], sleep=sleep):
            client.request_json("https://geo.test/search", params={"q": "Paris"})
    assert calls == [100.0, 115.1]
    assert client.request_json is request
    assert read_json(state)["network_requests"] == 2


def test_candidate_coordinates_are_provenance_and_do_not_assign_entity_qids(tmp_path):
    from GG_Data.pipeline.simplified_geography import candidate_records

    (tmp_path / "sources").mkdir()
    source.write_object(tmp_path / "progress.json", {"status": "RETRIEVED"})
    source.write_object(
        tmp_path / "sample.json", [{"place_id": "ent:paris", "name": "Paris"}]
    )
    for arm in ("native", "existing_dated"):
        source.write_object(
            tmp_path / f"sources/whg_{arm}.json",
            dict(
                response={
                    "ent:paris": {
                        "result": [
                            {"id": "place:wd:Q90", "name": "Paris"},
                            {"id": "place:wd:Q999", "name": "Unrelated"},
                        ]
                    }
                }
            ),
        )
    metadata = tmp_path / "native.json"
    source.write_object(
        metadata,
        {"Q90": {"id": "Q90", "claims": {}, "labels": {"en": {"value": "Paris"}}}},
    )

    class Client:
        def query(self, *args):
            raise AssertionError("All eligible native records are cached")

    result = candidate_records(tmp_path, metadata, Client())
    assert result["candidate_qids"] == 1 and result["identities_added"] == 0
    assert set(read_json(tmp_path / "candidate_records.json.gz")) == {"Q90"}
    assert read_json(tmp_path / "sample.json")[0]["place_id"] == "ent:paris"


def test_enriched_graph_keeps_native_polygon_and_all_original_pair_rows(tmp_path):
    from Agent.geo_agent.compact_format import records, write_graph
    from GG_Data.pipeline.simplified_geography import populate_geography

    model = tmp_path / "model"
    model.mkdir()
    entities = [
        dict(entity_id=source.entity_id(name, kind), name=name, type=kind, node_index=i)
        for i, (name, kind) in enumerate(
            [("Island", "LOC"), ("Unknown", "LOC"), ("Person", "PER")]
        )
    ]
    source.write_array(model / "entities.json.gz", entities)
    source.write_object(
        model / "manifest.json",
        dict(
            outputs={"entities.json.gz": digest(model / "entities.json.gz")},
            geography_status="PENDING_LAST_STAGE",
            counts={"entities": 3},
        ),
    )
    core = tmp_path / "core.json.gz"
    nodes = [
        dict(
            id=e["entity_id"],
            name=e["name"],
            type="location" if e["type"] == "LOC" else "person",
            attributes=dict(page_indices=[0], page_count=1),
        )
        for e in entities
    ]
    pairs = [[0, 1, 1, 1.0, 1.0], [0, 2, 1, 1.0, 1.0], [1, 2, 1, 1.0, 1.0]]
    source.write_array(tmp_path / "relations.json.gz", pairs)
    write_graph(
        core,
        dict(
            node_count=3,
            pair_count=3,
            raw_shared_page_count_sum=3,
            model_manifest_sha256=digest(model / "manifest.json"),
            page_scope_id="fixture",
        ),
        nodes,
        pairs,
    )
    polygon = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
    }
    rows = [
        dict(
            place_id=entities[0]["entity_id"],
            status="RESOLVED",
            crs="EPSG:3857",
            geometry=polygon,
        ),
        dict(place_id=entities[1]["entity_id"], status="UNRESOLVED", geometry=None),
    ]
    bad = tmp_path / "bad.json.gz"
    source.write_array(bad, rows)
    with pytest.raises(ValueError, match="CRS"):
        populate_geography(
            model, core, bad, tmp_path / "enriched_model", tmp_path / "enriched_graph"
        )
    assert not (tmp_path / "enriched_model").exists()
    rows[0]["crs"] = "EPSG:4326"
    good = tmp_path / "good.json.gz"
    source.write_array(good, rows)
    result = populate_geography(
        model, core, good, tmp_path / "enriched_model", tmp_path / "enriched_graph"
    )
    assert result["geography_processed"] == 2 and result["geography_resolved"] == 1
    saved = list(records(tmp_path / "enriched_graph/agent_graph.json.gz"))
    assert [r for k, r in saved if k == "pair"] == pairs
    saved_nodes = [r for k, r in saved if k == "node"]
    assert saved_nodes[0]["geometry"] == polygon
    assert saved_nodes[1]["geometry"] is None
    assert [r["id"] for r in saved_nodes] == [r["id"] for r in nodes]
    assert digest(core) == result["core_graph_sha256"]

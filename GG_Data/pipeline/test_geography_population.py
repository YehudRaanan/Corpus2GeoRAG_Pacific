"""New-model population reuses the approved selector and preserves identities."""

import gzip
import hashlib
import json
from types import SimpleNamespace

import geopandas as gpd
import pytest
from shapely.geometry import Point

from GG_Data.pipeline import geography_population as population
from GG_Data.pipeline.geography_comparison import prepare
from GG_Data.pipeline.geography_population import populate
from GG_Data.pipeline.geography_ranking_sample import wide_approximation
from GG_Data.pipeline.poc import digest, read_json


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "wt", encoding="utf-8") as stream:
        json.dump(value, stream)


@pytest.mark.parametrize("cached", [False, True])
def test_cache_only_ranking_stops_on_miss_and_reuses_receipts_in_place(
    tmp_path, monkeypatch, cached
):
    ranking = population.geography_ranking_sample
    base, comparison, cache = (tmp_path / n for n in ("base", "comparison", "cache"))
    cache.mkdir()
    target = dict(place_id="Q1", wikidata_id="Q1", name="Place", selection_date="1942")
    write(comparison / "sample.json", [target])
    write(comparison / "plan.json", dict(inputs={}))
    write(comparison / "progress.json", dict(status="RETRIEVED"))
    write(
        comparison / "evidence.json",
        {
            "Q1": dict(
                mention_id="m1",
                original_name="Place",
                text="Place",
                source_page="Page",
                context=dict(features=[]),
            )
        },
    )
    write(base / "entities/full_records.json.gz", {})
    write(comparison / "candidate_records.json.gz", {})
    write(
        comparison / "candidate_records_report.json",
        dict(
            outputs={
                "candidate_records.json.gz": digest(
                    comparison / "candidate_records.json.gz"
                )
            }
        ),
    )
    write(
        base / "mentions_pages/mentions.json.gz",
        [
            dict(
                mention_id="m1",
                start=0,
                word="Place",
                entity_group="LOC",
                wiki_site="enwiki",
                wiki_page_id=1,
            )
        ],
    )
    for arm in ("native", "existing_dated"):
        write(comparison / f"sources/whg_{arm}.json", dict(response={}))
    write(
        comparison / "sources/first_50_openhistoricalmap.json",
        dict(response=dict(elements=[])),
    )
    write(comparison / "sources" / population.osm_bigquery.NAME, {})
    monkeypatch.setattr(population.osm_bigquery, "load", lambda *args: [])
    monkeypatch.setattr(ranking, "ROOT", tmp_path)
    monkeypatch.setattr(ranking, "similarity", lambda left, right: float(left == right))

    def no_network(*args, **kwargs):
        raise AssertionError("Cache-only recovery must never call a source")

    url = "https://example.test/search"
    monkeypatch.setattr(
        ranking,
        "tools",
        lambda: SimpleNamespace(
            NOMINATIM={"OpenStreetMap": "https://example.test"}, request_json=no_network
        ),
    )
    params = dict(
        format="jsonv2",
        polygon_geojson="1",
        extratags="1",
        namedetails="1",
        addressdetails="1",
        q="Place",
        limit="10",
    )
    receipt = (
        cache
        / "sources"
        / (
            hashlib.sha256(
                json.dumps([url, params], sort_keys=True).encode()
            ).hexdigest()
            + ".json"
        )
    )
    if cached:
        write(
            receipt,
            dict(
                url=url,
                params=params,
                response=[
                    dict(
                        osm_type="node",
                        osm_id=7,
                        name="Place",
                        geojson=dict(type="Point", coordinates=[35, 32]),
                    )
                ],
            ),
        )
    before = {p: digest(p) for p in cache.rglob("*") if p.is_file()}
    output = tmp_path / "ranked"
    if not cached:
        with pytest.raises(ValueError, match="no saved request"):
            ranking.run(output, cache, comparison, base_dir=base, cache_only=True)
    else:
        result = ranking.run(output, cache, comparison, base_dir=base, cache_only=True)
        assert result["new_requests"] == 0 and result["reused_requests"] == 1
        assert result["inputs"] == result["geometry_proposals"] == 1
        assert read_json(output / "audit.json")["results"][0]["proposed"][
            "receipt"
        ] == str(receipt)
        assert not list((output / "sources").iterdir())
        assert read_json(output / "verification.json")["geometry_roundtrip_exact"]
    assert {p: digest(p) for p in cache.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("missing", [False, True])
def test_candidate_coordinates_use_current_only_after_snapshot_missing(
    tmp_path, monkeypatch, missing
):
    base, comparison = tmp_path / "base", tmp_path / "comparison"
    write(comparison / "progress.json", {"status": "RETRIEVED"})
    inputs = [{"place_id": "SYN_1", "wikidata_id": None, "name": "Place"}]
    write(comparison / "sample.json", inputs)
    for arm in ("native", "existing_dated"):
        write(
            comparison / f"sources/whg_{arm}.json",
            {
                "response": {
                    "SYN_1": {
                        "result": [
                            {"id": "place:wd:Q1", "name": "Place", "alt_names": []}
                        ]
                    }
                }
            },
        )
    write(base / "entities/full_records.json.gz", {})
    write(base / "matching/reference_manifest.json", {})
    monkeypatch.setattr(population, "ROOT", tmp_path)
    monkeypatch.setattr(population, "full_records", lambda *args: ({}, {}))
    calls = []

    def snapshot(qids, store, reference, **kwargs):
        assert qids == {"Q1"} and kwargs["allow_missing"]
        calls.append("snapshot")
        return {}, {"Q1": {"status": "MISSING"}}

    native = dict(id="Q1", type="item", claims={}, lastrevid=1, modified="2026-10-23")

    def current(store, url, params):
        assert params == {"action": "wbgetentities", "ids": "Q1", "format": "json"}
        calls.append("current")
        return {
            "entities": {"Q1": {"id": "Q1", "missing": ""} if missing else native}
        }, {"cache": "receipt"}

    monkeypatch.setattr(population, "acquire_missing", snapshot)
    monkeypatch.setattr(population.events, "cached_json", current)
    result = population.candidate_records(base, comparison)
    assert calls == ["snapshot", "current"]
    assert result["identities_added"] == 0
    assert result["missing_coordinate_records"] == (["Q1"] if missing else [])
    assert result["available_records"] == (0 if missing else 1)
    saved = read_json(comparison / "candidate_records.json.gz")
    assert saved == (
        {} if missing else {"Q1": {"requested_qid": "Q1", "entity": native}}
    )
    assert read_json(comparison / "sample.json") == inputs


def test_population_queries_use_new_model_only_and_keep_synthetic(tmp_path):
    base = tmp_path / "base"
    entities = [dict(entity_id=q, type="LOC") for q in ("Q1", "SYN_1")]
    entity_path = base / "model/entities.json.gz"
    write(entity_path, entities)
    write(
        base / "model/manifest.json",
        dict(outputs={entity_path.name: digest(entity_path)}),
    )
    targets, mentions = [], []
    for n, q in enumerate(("Q1", "SYN_1")):
        mentions.append(
            dict(
                mention_id=str(n),
                word="Place",
                Text="Place in Region",
                start=0,
                end=5,
                Source="Page",
                wiki_site="enwiki",
                wiki_page_id=1,
            )
        )
        targets.append(
            dict(
                place_id=q,
                name="Place",
                wikidata_id=q if q.startswith("Q") else None,
                selection_date="1942",
                source_context=[dict(mention_id=str(n))],
            )
        )
    write(base / "geography_inputs/targets.json", targets)
    write(base / "geography_inputs/report.json", {})
    write(base / "mentions_pages/mentions.json.gz", mentions)
    output = base / "retrieval"
    result = prepare(base, output, all_targets=True, model_dir=base / "model")
    assert result["input_count"] == 2
    assert result["all_existing_loc_targets"]
    assert read_json(output / "sample.json") == targets
    assert set(read_json(output / "queries.json")["native"]) == {"Q1", "SYN_1"}
    assert all(
        "model_qid_name" not in p and "geography_sample" not in p
        for p in result["inputs"]
    )


def test_wide_substitute_is_excluded_but_country_entity_and_local_geometry_remain():
    place = dict(name="Village", wikidata_id="Q1")
    country = dict(qid="Q2", aliases=["Country"], feature_code="country", tags={})
    assert wide_approximation(place, country)
    assert not wide_approximation(place | dict(wikidata_id="Q2"), country)
    assert not wide_approximation(
        place | dict(name="Country", wikidata_id=None), country
    )
    assert not wide_approximation(place, country | dict(feature_code="village"))


@pytest.mark.parametrize("with_mapping", [False, True])
def test_model_population_keeps_zero_score_geometry_and_all_existing_tables(
    tmp_path, with_mapping
):
    base, ranked, output = tmp_path / "base", tmp_path / "ranked", tmp_path / "final"
    model = base / "model"
    entities = [dict(entity_id=q, type="LOC", relevance=0.01) for q in ("Q1", "SYN_1")]
    write(model / "entities.json.gz", entities)
    write(model / "mentions.json.gz", [dict(entity_id="Q1")])
    hashes = {p.name: digest(p) for p in model.iterdir()}
    write(model / "manifest.json", dict(inputs={}, outputs=hashes))
    mapping_hashes = {}
    if with_mapping:
        # Generated catalogs were absent from the old table-only manifest.
        for name in (
            "RELATION_MAPPING_TABLE_v2.1.2.csv",
            "RELATION_DIRECTION_LOOKUP_v2.1.2.csv",
            "native_mapping_evidence.json",
        ):
            path = model / "mapping" / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b"original mapping bytes\r\n")
            mapping_hashes["mapping/" + name] = digest(path)
    chosen = dict(
        source="Wikidata",
        source_id="Q1$coord",
        qid="Q1",
        receipt="not_a_file",
        retrieved_at="2026-10-23T07:38:31+00:00",
        components=dict(qid=0),
        uncertainty_flags=["LOW_SUPPORT"],
        geometry_conversion=dict(method="ANTIMERIDIAN_SPLIT_V1"),
    )
    results = [
        dict(
            input=dict(place_id=q, name=q, type="LOC", selection_date="1942"),
            proposed=chosen if q == "Q1" else None,
            ranking=[dict(geometry_available=q == "Q1")],
        )
        for q in ("Q1", "SYN_1")
    ]
    write(ranked / "audit.json", dict(results=results))
    gpd.GeoDataFrame(
        [dict(place_id="Q1", geometry=Point(1, 2))], crs="EPSG:4326"
    ).to_parquet(ranked / "proposed_geometries.parquet")
    write(
        ranked / "verification.json",
        dict(outputs={p.name: digest(p) for p in ranked.iterdir()}),
    )
    result = populate(base, ranked, output)
    assert result["geography_rows"] == result["unresolved_geography"] == 1
    assert read_json(output / "entities.json.gz") == entities
    assert all(digest(output / n) == sha for n, sha in hashes.items())
    row = read_json(output / "geography.json.gz")[0]
    assert row["retrieved_at"] == chosen["retrieved_at"]
    assert (
        json.loads(row["decision_reason"])["geometry_conversion"]
        == chosen["geometry_conversion"]
    )
    assert row["geometry_ref"]["place_id"] == "Q1"
    assert row["geometry_ref"]["sha256"] == digest(output / "geometries.parquet")
    assert len(gpd.read_parquet(output / "geometries.parquet").columns) == 13
    assert read_json(output / "verification.json")["all_previous_tables_unchanged"]
    assert all(
        digest(output / name) == sha == result["outputs"][name]
        for name, sha in mapping_hashes.items()
    )
    verification = read_json(output / "verification.json")
    assert verification["mapping_artifacts"] == mapping_hashes
    assert verification["mapping_artifacts_unchanged"]

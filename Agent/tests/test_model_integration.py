"""Approved graph S2T interfaces: typed identities and model-only Shapely."""

import gzip
import hashlib
import json

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from GG_Data.pipeline import graph_contract
from geo_agent.agent import AgentAnswer, collect_evidence, confidence, finalize_answer
from geo_agent.graph_store import Edge, GraphStore, Node
from langchain_core.messages import HumanMessage, ToolMessage


def typed_store():
    nodes = [
        Node(id="Q1::LOC", wikidata_id="Q1", name="Place", type="location"),
        Node(id="Q1::ORG", wikidata_id="Q1", name="Place", type="org"),
        Node(id="Q2::event", wikidata_id="Q2", name="Event", type="event"),
    ]
    edges = [
        Edge(id="assertion-1", source="Q2", target="Q1", type="wd:P276"),
        Edge(
            id="assertion-1::reverse",
            source_edge_id="assertion-1",
            source="Q1",
            target="Q2",
            type="inverse:wd:P276",
        ),
    ]
    return GraphStore(nodes, edges, geometries={"Q1::LOC": box(139, 35, 140, 36)})


def test_typed_qid_edges_resolve_without_assertion_copies():
    store = typed_store()
    assert len(store.nodes) == 3 and len(store.edges) == 2
    assert store.schema()["assertion_count"] == 1
    assert store.out_edges["Q1"][0] is store.out_edges["Q1::LOC"][0]
    assert store.out_edges["Q1"][0] is store.out_edges["Q1::ORG"][0]
    for source in ("Q1", "Q1::LOC", "Q1::ORG"):
        rows = store.find_relations(source_id=source, relation_type="inverse:wd:P276")
        assert len(rows) == 1 and rows[0]["assertion_id"] == "assertion-1"
        assert {n["id"] for n in rows[0]["source"]["entities"]} == {
            "Q1::LOC",
            "Q1::ORG",
        }
    assert len(store.find_relations(target_id="Q1::ORG", relation_type="wd:P276")) == 1
    assert (
        len(
            store.neighbors(
                "Q2::event", relation_types=["wd:P276"], neighbor_type="org"
            )
        )
        == 1
    )
    assert {n["id"] for n in store.get_entity("Q1")["entities"]} == {
        "Q1::LOC",
        "Q1::ORG",
    }
    assert store.search_entities("Place", type="org")[0]["id"] == "Q1::ORG"


def test_typed_spatial_traversal_and_shared_reverse_evidence():
    store = typed_store()
    assert [n["id"] for n in store.locations_of("Q2::event")] == ["Q1::LOC"]
    assert store.distance_km("Q1::LOC", 35.5, 139.5) == 0
    assert [e["id"] for e in store.what_happened_at(35.5, 139.5, 1)["events"]] == [
        "Q2::event"
    ]
    assert (
        store.to_geojson(["Q2::event"])["features"][0]["geometry"]["type"] == "Polygon"
    )
    rows = store.find_relations()
    evidence = collect_evidence([("find_relations", rows)])
    assert len(evidence["edges"]) == 1
    assert (
        confidence(["Q1::ORG"], [], evidence["edges"], False)["basis"]["max_edge_count"]
        == 1
    )
    turn = [
        HumanMessage(content="Show Place"),
        ToolMessage(
            name="find_relations", tool_call_id="one", content=json.dumps(rows)
        ),
    ]
    result = finalize_answer(
        store,
        AgentAnswer(answer="Place", answer_ids=["Q1"], context_ids=[], sources=[]),
        turn,
    )
    assert result["answer_ids"] == ["Q1::LOC", "Q1::ORG"]


def test_invalid_endpoints_and_reverse_views_fail_explicitly():
    store = typed_store()
    with pytest.raises(ValueError, match="Unknown graph edge endpoint"):
        GraphStore(
            list(store.nodes.values()),
            [Edge(source="Q2", target="Q999", type="wd:P276")],
        )
    with pytest.raises(ValueError, match="Invalid reverse assertion"):
        GraphStore(
            list(store.nodes.values()),
            [
                Edge(
                    id="bad",
                    source="Q2",
                    target="Q1",
                    type="wd:P276",
                    source_edge_id="missing",
                )
            ],
        )


def test_exported_relation_catalog_is_exposed_unchanged(tmp_path):
    store = typed_store()
    catalog = {
        "wd:P276": {"label": "location", "level1_families": ["SPATIAL"]},
        "inverse:wd:P276": {
            "label": "inverse of location",
            "level1_families": ["SPATIAL"],
        },
    }
    graph = tmp_path / "graph.json"
    graph.write_text(
        json.dumps(
            {
                "relation_catalog": catalog,
                "nodes": [
                    n.model_dump(exclude_none=True) for n in store.nodes.values()
                ],
                "edges": [e.model_dump(exclude_none=True) for e in store.edges],
            }
        ),
        encoding="utf-8",
    )
    loaded = GraphStore.from_json(graph)
    assert loaded.schema()["relation_catalog"] == catalog
    assert loaded.relation_id("wd:P276") == "wd:P276"


def test_model_geometry_batch_is_exact_and_reads_once(tmp_path, monkeypatch):
    frame = gpd.GeoDataFrame(
        {"place_id": ["Q1", "SYN_second"]},
        geometry=[box(139, 35, 140, 36), Point(2, 3)],
        crs="EPSG:4326",
    )
    path = tmp_path / "geometries.parquet"
    frame.to_parquet(path, index=False)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    pointers = [
        {"file": path.name, "place_id": p, "sha256": sha} for p in frame.place_id
    ]
    reads = []
    original = graph_contract.gpd.read_parquet
    monkeypatch.setattr(
        graph_contract.gpd, "read_parquet", lambda p: (reads.append(p), original(p))[1]
    )
    loaded = graph_contract.load_geometries(
        pointers, tmp_path, required_crs="EPSG:4326"
    )
    assert len(reads) == 1
    assert all(
        loaded[p].equals_exact(g, 0) for p, g in zip(frame.place_id, frame.geometry)
    )
    with pytest.raises(ValueError, match="Duplicate geometry reference"):
        graph_contract.load_geometries([pointers[0], pointers[0]], tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        graph_contract.load_geometries(
            [pointers[0], {**pointers[1], "sha256": "b" * 64}], tmp_path
        )
    with pytest.raises(ValueError, match="CRS is incompatible"):
        graph_contract.load_geometries(pointers, tmp_path, required_crs="EPSG:3857")
    graph = tmp_path / "graph.json"
    store = typed_store()
    nodes = list(store.nodes.values()) + [
        Node(id="SYN_second", name="Second", type="location")
    ]
    graph.write_text(
        json.dumps(
            {
                "nodes": [n.model_dump(exclude_none=True) for n in nodes],
                "edges": [e.model_dump(exclude_none=True) for e in store.edges],
            }
        ),
        encoding="utf-8",
    )
    with gzip.open(tmp_path / "geography.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(
            [{"place_id": p["place_id"], "geometry_ref": p} for p in pointers], stream
        )
    restored = GraphStore.from_json(graph, model_dir=tmp_path)
    assert restored.geoms["Q1::LOC"].equals_exact(frame.geometry.iloc[0], 0)
    assert "Q1::ORG" not in restored.geoms
    assert all(n.geometry is None for n in restored.nodes.values())
    assert not any("geometry_ref" in n for n in json.loads(graph.read_text())["nodes"])

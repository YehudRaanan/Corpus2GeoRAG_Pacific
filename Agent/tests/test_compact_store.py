"""Complete co-occurrence queries without loading all edges into memory."""

import gzip
import json

import pytest
from geo_agent.graph_store import GraphStore


def test_enriched_acceptance_checks_native_geometry_and_unknown_locations(tmp_path):
    from geo_agent.compact_format import write_graph
    from geo_agent.verify_compact import verify

    polygon = dict(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]])
    nodes = [
        dict(
            id=key,
            name=key,
            type=kind,
            geometry=geometry,
            attributes=dict(page_count=1, page_indices=[0], geography_status=status),
        )
        for key, kind, geometry, status in [
            ("island", "location", polygon, "RESOLVED"),
            ("unknown", "location", None, "UNRESOLVED_NO_ELIGIBLE_SOURCE_GEOMETRY"),
            ("person", "person", None, None),
        ]
    ]
    path = tmp_path / "enriched.json.gz"
    write_graph(
        path,
        dict(
            node_count=3,
            pair_count=3,
            raw_shared_page_count_sum=3,
            page_scope_id="fixture",
            geography_status="COMPLETE_WITH_UNRESOLVED",
        ),
        nodes,
        [[0, 1, 1, 1.0, 1.0], [0, 2, 1, 1.0, 1.0], [1, 2, 1, 1.0, 1.0]],
    )
    result = verify(path, tmp_path / "acceptance.json")
    assert result["geography"]["locations"] == 2
    assert result["geography"]["geometry_types"] == {"Polygon": 1}
    assert len(result["geography"]["geometry_rows_sha256"]) == 64
    assert result["geography"]["spatial_checks"][0]["geometry_type"] == "Polygon"
    assert (
        result["geography"]["status_counts"]["UNRESOLVED_NO_ELIGIBLE_SOURCE_GEOMETRY"]
        == 1
    )


def fixture_graph(tmp_path, invalid=False):
    from geo_agent.compact_format import write_graph

    nodes = [
        dict(id=n, name=n, type=t, attributes={"page_count": c, "page_indices": pages})
        for n, t, c, pages in [
            ("a", "person", 4, [0, 1, 2, 3]),
            ("b", "org", 5, [0, 1, 4, 5, 6]),
            ("e", "event", 1, [0]),
            ("f", "event", 2, [0, 6]),
        ]
    ]
    pairs = [
        [0, 1, 2, 0.5, 0.4],
        [0, 2, 1, 0.25, 1.0],
        [0, 3, 1, 0.25, 0.5],
        [1, 2, 1, 0.2, 1.0],
        [1, 3, 2, 0.4, 1.0],
        [2, 3, 1, 1.0, 0.5],
    ]
    if invalid:
        pairs[0][1] = 9
    path = tmp_path / "graph.json.gz"
    write_graph(
        path,
        dict(
            node_count=4,
            pair_count=6,
            raw_shared_page_count_sum=8,
            page_scope_id="fixture",
            geography_status="PENDING_LAST_STAGE",
        ),
        nodes,
        pairs,
    )
    return path


def test_compact_tools_work_in_async_agent_worker_threads(tmp_path):
    import asyncio

    from geo_agent.tools import build_tools

    store = GraphStore.from_json(fixture_graph(tmp_path))
    tools = {tool.name: tool for tool in build_tools(store)}

    async def invoke():
        return await asyncio.gather(
            tools["find_relations"].ainvoke(dict(source_id="a", target_id="b")),
            tools["get_entity"].ainvoke(dict(entity_id="a")),
            tools["get_neighbors"].ainvoke(dict(entity_id="a", direction="in")),
        )

    try:
        pair, entity, neighbors = map(json.loads, asyncio.run(invoke()))
        assert pair[0]["strength"] == 0.5 and pair[0]["count"] == 2
        assert entity["id"] == "a" and entity["degree"] == 3
        assert neighbors[0]["neighbor"]["id"] == "e"
    finally:
        store.connection.close()


def test_compact_graph_loads_complete_directed_queries_and_integer_counts(tmp_path):
    path = fixture_graph(tmp_path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        assert len(json.load(stream)["edges"]) == 6
    store = GraphStore.from_json(path)
    assert store.schema()["edge_count"] == 12
    assert store.schema()["assertion_count"] == 6
    forward = store.find_relations(source_id="a", target_id="b")[0]
    reverse = store.find_relations(source_id="b", target_id="a")[0]
    assert forward["strength"] == 0.5 and reverse["strength"] == 0.4
    assert type(forward["count"]) is int and forward["count"] == reverse["count"] == 2
    assert forward["shared_page_indices"] == [0, 1]
    assert forward["semantics"] == "PAGE_CO_OCCURRENCE_ONLY"
    # The event appearing on one page is stronger as a SOURCE than a repeated org.
    incoming = store.neighbors("a", direction="in")
    assert incoming[0]["neighbor"]["id"] == "e" and incoming[0]["strength"] == 1
    assert store.find_relations(source_id="e", target_id="f")[0]["strength"] == 1
    assert store.find_relations(source_id="e", target_id="a")[0]["strength"] == 1
    assert store.find_relations(relation_type="PARTICIPATED_IN") == []
    assert store.find_relations(date_from="1941") == []
    assert store.get_entity("a")["degree"] == 3
    assert len(store.edges) == 0  # All logical pairs are held by the disk index.
    again = GraphStore.from_json(path)
    assert again.find_relations(source_id="a", target_id="b") == [forward]


def test_compact_graph_rejects_bad_endpoints_and_invalid_json_tail(tmp_path):
    path = fixture_graph(tmp_path, invalid=True)
    with pytest.raises(ValueError, match="endpoint"):
        GraphStore.from_json(path)


@pytest.mark.parametrize("damage", ["tail", "strength", "count", "missing_pair"])
def test_compact_graph_rejects_corrupt_evidence(tmp_path, damage):
    path = fixture_graph(tmp_path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        raw = stream.read()
    if damage == "tail":
        raw += "{}"
    elif damage == "strength":
        raw = raw.replace("[0,1,2,0.5,0.4]", "[0,1,2,0.8,0.4]")
    elif damage == "count":
        raw = raw.replace("[0,1,2,0.5,0.4]", "[0,1,3,0.75,0.6]")
    else:
        raw = raw.replace("[0,1,2,0.5,0.4],\n", "").replace(
            '"pair_count":6', '"pair_count":5'
        )
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(raw)
    with pytest.raises(ValueError):
        GraphStore.from_json(path)


def test_compact_graph_tools_return_directional_strength(tmp_path):
    from geo_agent.tools import build_tools

    store = GraphStore.from_json(fixture_graph(tmp_path))
    tools = {tool.name: tool for tool in build_tools(store)}
    row = json.loads(
        tools["find_relations"].invoke(dict(source_id="b", target_id="a"))
    )[0]
    assert row["strength"] == 0.4 and row["count"] == 2
    assert "does not establish" in tools["get_locations"].description
    assert "strength" in tools["find_relations"].description
    from geo_agent.agent import SYSTEM_PROMPT

    assert "PAGE_CO_OCCURRENCE_ONLY" in SYSTEM_PROMPT


def test_complete_graph_verification_report(tmp_path):
    from geo_agent.verify_compact import verify

    path = fixture_graph(tmp_path)
    report = tmp_path / "acceptance.json"
    result = verify(path, report)
    assert result["status"] == "PASS"
    assert result["coverage"]["pair_count"] == 6
    assert result["coverage"]["raw_shared_page_count_sum"] == 8
    assert sum(result["coverage"]["pair_categories"].values()) == 6
    assert len(result["tool_checks"]) == 8  # Four type categories, both directions.
    assert json.loads(report.read_text())["graph_sha256"] == result["graph_sha256"]
    with pytest.raises(FileExistsError):
        verify(path, report)

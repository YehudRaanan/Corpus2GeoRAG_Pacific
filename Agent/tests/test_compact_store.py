"""Complete co-occurrence queries without loading all edges into memory."""

import gzip
import json

import pytest
from geo_agent.graph_store import GraphStore


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
    pairs = [[0, 1, 2, 0.5, 0.4], [0, 2, 1, 0.25, 1.0], [2, 3, 1, 1.0, 0.5]]
    if invalid:
        pairs[0][1] = 9
    path = tmp_path / "graph.json.gz"
    write_graph(
        path,
        dict(
            node_count=4,
            pair_count=3,
            page_scope_id="fixture",
            geography_status="PENDING_LAST_STAGE",
        ),
        nodes,
        pairs,
    )
    return path


def test_compact_graph_loads_complete_directed_queries_and_integer_counts(tmp_path):
    path = fixture_graph(tmp_path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        assert len(json.load(stream)["edges"]) == 3
    store = GraphStore.from_json(path)
    assert store.schema()["edge_count"] == 6
    assert store.schema()["assertion_count"] == 3
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
    assert store.get_entity("a")["degree"] == 2
    assert len(store.edges) == 0  # All three logical pairs are held by the disk index.
    again = GraphStore.from_json(path)
    assert again.find_relations(source_id="a", target_id="b") == [forward]


def test_compact_graph_rejects_bad_endpoints_and_invalid_json_tail(tmp_path):
    path = fixture_graph(tmp_path, invalid=True)
    with pytest.raises(ValueError, match="endpoint"):
        GraphStore.from_json(path)


@pytest.mark.parametrize("damage", ["tail", "strength", "count"])
def test_compact_graph_rejects_corrupt_evidence(tmp_path, damage):
    path = fixture_graph(tmp_path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        raw = stream.read()
    if damage == "tail":
        raw += "{}"
    elif damage == "strength":
        raw = raw.replace("[0,1,2,0.5,0.4]", "[0,1,2,0.8,0.4]")
    else:
        raw = raw.replace("[0,1,2,0.5,0.4]", "[0,1,3,0.75,0.6]")
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

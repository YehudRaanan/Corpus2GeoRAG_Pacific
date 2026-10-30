"""Exact-ID attachment and real Agent spatial regression checks."""

import gzip
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path

import pytest

from Agent.geo_agent.compact_format import records, write_graph
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.simplified_agent import write_array, write_object
from GG_Data.pipeline.simplified_xy_attach import attach, update_node


@pytest.fixture
def inputs(tmp_path):
    graph = tmp_path / "core.json.gz"
    nodes = [
        dict(
            id=key,
            name=name,
            type=kind,
            text="source text",
            attributes=dict(
                page_indices=[0],
                page_count=1,
                geography_status="PENDING_LAST_STAGE",
                event_dates={"native": "preserved"},
                owner_value=17,
            ),
        )
        for key, name, kind in [
            ("loc:1", "Island", "location"),
            ("event:Q1", "Landing", "event"),
            ("loc:2", "Unknown", "location"),
            ("per:1", "Person", "person"),
        ]
    ]
    pairs = [[a, b, 1, 1.0, 1.0] for a in range(4) for b in range(a + 1, 4)]
    write_graph(
        graph,
        dict(
            node_count=4,
            pair_count=6,
            raw_shared_page_count_sum=6,
            model_manifest_sha256="core-hash",
            pages=[],
            geography_status="PENDING_LAST_STAGE",
        ),
        nodes,
        pairs,
    )
    acceptance = tmp_path / "accepted.json"
    pair_hash = hashlib.sha256(
        b"".join(struct.pack("<qqqdd", *p) for p in pairs)
    ).hexdigest()
    write_object(
        acceptance,
        dict(
            status="PASS",
            graph_sha256=digest(graph),
            node_count=4,
            verification="ALL_PAIRS_MEMBERSHIP_WEIGHTS_UNIQUENESS_AND_CONSERVATION",
            coverage=dict(pair_count=6, pair_rows_sha256=pair_hash),
        ),
    )
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    rows = [
        dict(
            entity_id=n["id"],
            name=n["name"],
            type=kind,
            status="SOURCE_POINT_SELECTED_ARBITRARILY",
            x=x,
            y=y,
            geometry=dict(type="Point", coordinates=[x, y]),
            crs="EPSG:4326",
            identity_verified=False,
            selection_method="OWNER_ARBITRARY_FIRST_AVAILABLE",
            source="fixture",
            coordinate_method="FIRST_SOURCE_GEOMETRY_VERTEX",
            source_geometry=dict(
                type="LineString", coordinates=[[x, y], [x + 1, y + 1]]
            ),
        )
        for n, kind, x, y in [(nodes[0], "LOC", 10, 20), (nodes[1], "event", 30, 40)]
    ]
    rows.append(
        dict(
            entity_id="loc:2",
            name="Unknown",
            type="LOC",
            status="NO_LOCAL_EXACT_SOURCE_COORDINATE",
            identity_verified=False,
        )
    )
    write_array(overlay / "xy_overlay.json.gz", rows)
    bind_overlay(overlay)
    return graph, acceptance, overlay, tmp_path / "attached", nodes


def bind_overlay(folder):
    sha = digest(folder / "xy_overlay.json.gz")
    (folder / "manifest.json").write_text(
        json.dumps(
            dict(
                core_model_manifest_sha256="core-hash",
                outputs={"xy_overlay.json.gz": sha},
            )
        ),
        encoding="utf-8",
    )
    (folder / "verification.json").write_text(
        json.dumps(
            dict(
                status="VERIFIED_LOCAL_OVERLAY_IDS_SOURCE_HASHES_AND_PRESERVED_ROWS",
                overlay_sha256=sha,
                manifest_sha256=digest(folder / "manifest.json"),
            )
        ),
        encoding="utf-8",
    )


def tail(path):
    with gzip.open(path, "rb") as stream:
        return stream.read().split(b'"edges":[', 1)[1]


def test_actual_overlay_producer_lowercase_event_schema_is_accepted(tmp_path):
    from GG_Data.pipeline.simplified_xy import build

    model, ranking = tmp_path / "model", tmp_path / "ranking"
    model.mkdir()
    ranking.mkdir()
    identity = dict(entity_id="event:Q1", name="Landing", type="event")
    write_array(model / "entities.json.gz", [identity])
    write_array(
        model / "event_events.json.gz",
        [dict(entity_id="event:Q1", native_records=[dict(qid="Q1")])],
    )
    write_array(model / "entity_exclusions.json.gz", [])
    write_object(
        model / "manifest.json",
        dict(outputs={p.name: digest(p) for p in model.iterdir()}),
    )
    write_object(ranking / "audit.json", dict(results=[]))
    write_object(
        ranking / "verification.json",
        dict(
            status="VERIFIED_RANKING_PROPOSALS",
            inputs=0,
            outputs={"audit.json": digest(ranking / "audit.json")},
        ),
    )
    native = tmp_path / "native.json"
    write_object(
        native,
        {
            "Q1": dict(
                id="Q1",
                claims={
                    "P625": [
                        dict(
                            id="Q1$native",
                            rank="normal",
                            qualifiers={"original": [1]},
                            mainsnak=dict(
                                datavalue=dict(
                                    value=dict(
                                        longitude=30,
                                        latitude=40,
                                        globe="http://www.wikidata.org/entity/Q2",
                                        precision=0.1,
                                    )
                                )
                            ),
                        )
                    ]
                },
            )
        },
    )
    build(model, ranking, native, tmp_path / "produced")
    row = read_json(tmp_path / "produced/xy_overlay.json.gz")[0]
    assert row["type"] == "event"
    node = dict(
        id=row["entity_id"],
        name=row["name"],
        type="event",
        attributes=dict(event_dates={"preserve": True}),
    )
    attached = update_node(node, row)
    assert attached["geometry"] == dict(type="Point", coordinates=[30, 40])
    assert attached["attributes"]["event_dates"] == node["attributes"]["event_dates"]
    assert attached["attributes"]["xy_source"]["chosen_statement"]["qualifiers"] == {
        "original": [1]
    }


def test_attach_preserves_non_geo_nodes_dates_and_exact_edge_bytes(inputs):
    graph, acceptance, overlay, output, nodes = inputs
    result = attach(graph, acceptance, overlay, output)
    reader = records(output / "agent_graph.json.gz")
    _, metadata = next(reader)
    actual = [next(reader)[1] for _ in nodes]
    assert metadata["geography_status"] == "PARTIAL_ARBITRARY_SOURCE_POINTS"
    assert tail(graph) == tail(output / "agent_graph.json.gz")
    assert result["edge_tail_sha256"] == hashlib.sha256(tail(graph)).hexdigest()
    for before, after in zip(nodes, actual):
        after = dict(after)
        if before["type"] in {"location", "event"}:
            after.pop("geometry")
            attrs = dict(after["attributes"])
            attrs.pop("xy_source")
            attrs["geography_status"] = "PENDING_LAST_STAGE"
            after["attributes"] = attrs
        assert before == after
    assert actual[2]["geometry"] is None
    assert (
        actual[0]["attributes"]["xy_source"]["source_geometry"]["type"] == "LineString"
    )
    with pytest.raises(FileExistsError):
        attach(graph, acceptance, overlay, output)


@pytest.mark.parametrize(
    "damage", ["foreign", "name", "binding", "invalid_xy", "accepted_hash"]
)
def test_rejects_unbound_or_foreign_overlay(inputs, damage):
    graph, acceptance, overlay, output, _ = inputs
    rows = read_json(overlay / "xy_overlay.json.gz")
    if damage == "foreign":
        rows[0]["entity_id"] = "foreign"
    elif damage == "name":
        rows[0]["name"] = "Different"
    elif damage == "invalid_xy":
        rows[0]["geometry"]["coordinates"] = [181, 20]
    elif damage == "accepted_hash":
        proof = read_json(acceptance)
        proof["graph_sha256"] = "wrong"
        acceptance.write_text(json.dumps(proof), encoding="utf-8")
    else:
        (overlay / "xy_overlay.json.gz").write_bytes(b"changed")
    if damage in {"foreign", "name", "invalid_xy"}:
        with gzip.open(
            overlay / "xy_overlay.json.gz", "wt", encoding="utf-8"
        ) as stream:
            json.dump(rows, stream)
        bind_overlay(overlay)
    with pytest.raises(ValueError):
        attach(graph, acceptance, overlay, output)
    assert not (output / "manifest.json").exists()


def test_attached_points_work_with_actual_agent_loc_and_event_near_and_bbox(inputs):
    python = Path(os.environ.get("GEOAI_AGENT_PYTHON", ""))
    if not python.is_file():
        pytest.skip("Set GEOAI_AGENT_PYTHON to existing Agent environment")
    graph, acceptance, overlay, output, _ = inputs
    attach(graph, acceptance, overlay, output)
    script = """
import json, sys
from geo_agent.compact_store import CompactGraphStore
from geo_agent.tools import build_tools
store = CompactGraphStore.load(sys.argv[1])
tools = {t.name:t for t in build_tools(store)}
try:
    for key, kind, x, y in [("loc:1","location",10,20),("event:Q1","event",30,40)]:
        for name, args in [("entities_near",dict(lat=y,lon=x,radius_km=.001,type=kind)),
                           ("entities_in_bbox",dict(min_lon=x-.01,min_lat=y-.01,max_lon=x+.01,max_lat=y+.01,type=kind))]:
            hits = json.loads(tools[name].invoke(args))
            assert key in {r["id"] for r in hits}, (name, key, hits)
    assert store.nodes["loc:2"].geometry is None
finally:
    store.connection.close()
"""
    checked = subprocess.run(
        [str(python), "-c", script, str(output / "agent_graph.json.gz")],
        cwd=ROOT / "Agent",
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr

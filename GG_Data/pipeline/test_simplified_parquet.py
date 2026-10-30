"""Parquet preserves complete compact graph values and source bindings."""

import hashlib
import json
import shutil
import struct
import subprocess
import sys

import pyarrow.parquet as pq
import pytest

from Agent.geo_agent.compact_format import records, write_graph
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.simplified_agent import write_object
from GG_Data.pipeline.simplified_parquet import convert, restore, verify


@pytest.fixture
def graph_inputs(tmp_path):
    graph = tmp_path / "source.json.gz"
    nodes = [
        dict(
            id="loc:1",
            name="Tōkyō",
            type="location",
            geometry=None,
            attributes=dict(
                page_indices=[0],
                page_count=1,
                custom=[None, True, 3.5],
                geography_status="PENDING_LAST_STAGE",
            ),
        ),
        dict(
            id="event:Q1",
            name="Landing",
            type="event",
            sources=[],
            attributes=dict(
                page_indices=[0, 1],
                page_count=2,
                event_dates=dict(native=dict(precision=9, value="+1941-00-00")),
            ),
        ),
    ]
    pairs = [[0, 1, 1, 1.0, 0.5]]
    metadata = dict(
        node_count=2,
        pair_count=1,
        raw_shared_page_count_sum=1,
        geography_status="PENDING_LAST_STAGE",
        pages=[dict(page_index=0)],
        nested=dict(custom=[True, None, 7]),
    )
    write_graph(graph, metadata, nodes, pairs)
    proof = tmp_path / "accepted.json"
    write_object(
        proof,
        dict(
            status="PASS",
            graph_sha256=digest(graph),
            node_count=2,
            verification="ALL_PAIRS_MEMBERSHIP_WEIGHTS_UNIQUENESS_AND_CONSERVATION",
            coverage=dict(
                pair_count=1,
                raw_shared_page_count_sum=1,
                pair_rows_sha256=hashlib.sha256(
                    struct.pack("<qqqdd", *pairs[0])
                ).hexdigest(),
            ),
        ),
    )
    return graph, proof, tmp_path / "parquet"


def test_full_value_roundtrip_preserves_original_metadata_node_fields_and_pairs(
    graph_inputs,
):
    graph, proof, output = graph_inputs
    result = convert(graph, proof, output, batch_size=1)
    assert result["status"] == "VERIFIED_PARQUET_VALUES"
    assert result["geography_status"] == "PENDING_LAST_STAGE"
    assert result["node_count"] == 2 and result["pair_count"] == 1
    parquet = output / "graph.parquet"
    checked = verify(parquet, result)
    assert checked["node_rows_sha256"] == result["node_rows_sha256"]
    restored = output / "restored.json.gz"
    restore(parquet, output / "manifest.json", restored)
    assert list(records(graph)) == list(records(restored))
    assert pq.ParquetFile(parquet).metadata.num_rows == 3
    with pytest.raises(FileExistsError):
        convert(graph, proof, output)
    with pytest.raises(FileExistsError):
        restore(parquet, output / "manifest.json", restored)


def test_changed_accepted_source_is_rejected(graph_inputs):
    graph, proof, output = graph_inputs
    changed = read_json(proof)
    changed["graph_sha256"] = "wrong"
    proof.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="acceptance"):
        convert(graph, proof, output)
    assert not output.exists()


def test_module_restore_requires_manifest_before_publishing_any_output(graph_inputs):
    graph, proof, output = graph_inputs
    convert(graph, proof, output, batch_size=1)
    restored = output / "unverified.json.gz"
    with pytest.raises(TypeError):
        restore(output / "graph.parquet", restored)
    assert not restored.exists()


def test_portable_restore_runs_without_project_checkout_and_rejects_changed_values(
    graph_inputs, tmp_path
):
    delivery = (
        __import__("pathlib").Path(__file__).parents[2]
        / "Data/external/simplified_agent_20261030/core_parquet_v1"
    )
    if not delivery.is_dir():
        pytest.skip("Requires the locally prepared portable Parquet delivery")
    graph, proof, output = graph_inputs
    result = convert(graph, proof, output, batch_size=1)
    portable = tmp_path / "standalone"
    portable.mkdir()
    for name in ["restore.py", "compact_format.py"]:
        shutil.copyfile(delivery / name, portable / name)
    shutil.copyfile(output / "graph.parquet", portable / "graph.parquet")
    shutil.copyfile(output / "manifest.json", portable / "manifest.json")
    command = [
        sys.executable,
        str(portable / "restore.py"),
        "graph.parquet",
        "manifest.json",
        "restored.json.gz",
    ]
    checked = subprocess.run(command, cwd=portable, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert list(records(graph)) == list(records(portable / "restored.json.gz"))
    checked = subprocess.run(command, cwd=portable, capture_output=True, text=True)
    assert checked.returncode != 0
    # Change a pair and rebind only the file hash: the full value proof must fail
    # before an atomic restored graph can be published.
    import pyarrow as pa

    table = pq.read_table(portable / "graph.parquet")
    rows = table.to_pylist()
    rows[-1]["strength_target_source"] = 0.75
    pq.write_table(
        pa.Table.from_pylist(rows, schema=table.schema), portable / "graph.parquet"
    )
    result["outputs"]["graph.parquet"] = digest(portable / "graph.parquet")
    (portable / "manifest.json").write_text(json.dumps(result), encoding="utf-8")
    command[-1] = "damaged.json.gz"
    checked = subprocess.run(command, cwd=portable, capture_output=True, text=True)
    assert checked.returncode != 0
    assert "pair proof differs" in checked.stderr
    assert not (portable / "damaged.json.gz").exists()
    with pytest.raises(ValueError, match="pair proof differs"):
        restore(
            portable / "graph.parquet",
            portable / "manifest.json",
            portable / "module_damaged.json.gz",
        )
    assert not (portable / "module_damaged.json.gz").exists()


@pytest.mark.parametrize("damage", ["pair", "node", "row_order", "metadata"])
def test_readback_rejects_value_or_metadata_corruption(graph_inputs, damage):
    graph, proof, output = graph_inputs
    expected = convert(graph, proof, output, batch_size=1)
    table = pq.read_table(output / "graph.parquet")
    rows = table.to_pylist()
    schema = table.schema
    if damage == "pair":
        rows[-1]["strength_target_source"] = 0.75
    elif damage == "node":
        rows[0]["node_json"] = '{"id":"changed"}'
    elif damage == "row_order":
        rows[0], rows[-1] = rows[-1], rows[0]
    else:
        metadata = dict(schema.metadata)
        metadata[b"geoai.source_graph_sha256"] = b"wrong"
        schema = schema.with_metadata(metadata)
    damaged = output / "damaged.parquet"
    import pyarrow as pa

    pq.write_table(pa.Table.from_pylist(rows, schema=schema), damaged)
    with pytest.raises(ValueError):
        verify(damaged, expected)

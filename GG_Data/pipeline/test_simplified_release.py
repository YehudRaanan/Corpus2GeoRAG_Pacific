"""Cross-environment smoke test of model -> real Agent -> portable release."""

import os
import shutil
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.simplified_agent import prepare, write_array, write_object
from GG_Data.pipeline.simplified_page_events import assemble
from GG_Data.pipeline.simplified_relations import build_graph
from GG_Data.pipeline.simplified_verify import verify_and_package, verify_raw_rows


def test_complete_release_loads_real_agent_and_contains_all_model_and_adapter_files(
    tmp_path,
):
    python = Path(os.environ.get("GEOAI_AGENT_PYTHON", ""))
    if not python.is_file():
        pytest.skip("Set GEOAI_AGENT_PYTHON to the existing Agent environment")
    rows = [
        dict(
            word=word,
            entity_group=kind,
            score=1.0,
            start=0,
            end=len(word),
            Source=page,
            Index=i,
            Text=word,
            subtype=kind,
        )
        for i, (word, kind, page) in enumerate(
            [("A", "PER", "Q1"), ("Island", "LOC", "Q1"), ("1941", "DATE", "Q2")]
        )
    ]
    parquet = tmp_path / "input.parquet"
    pq.write_table(pa.Table.from_pylist(rows), parquet)
    prepared = tmp_path / "prepared"
    prepare(parquet, prepared, expected_sha256=digest(parquet))
    write_object(tmp_path / "raw_verification.json", verify_raw_rows(prepared))
    pages, links, hierarchy = (
        tmp_path / name
        for name in ["page_acquisition", "page_link_metadata", "hierarchy"]
    )
    for folder in [pages, links, hierarchy]:
        folder.mkdir()
    page_rows = []
    for row in read_json(prepared / "wiki_pages.json.gz"):
        raw = pages / f"raw_{row['page_index']}.txt"
        raw.write_text("[[Event]]", encoding="utf-8")
        page_rows.append(
            dict(
                row,
                title="Page " + str(row["page_index"]),
                wiki_page_id=row["page_index"] + 10,
                revision_id=row["page_index"] + 100,
                status="AVAILABLE",
                evidence="fixture",
                raw_path=str(raw),
                raw_sha256=digest(raw),
                links=["Event"],
            )
        )
    write_array(pages / "page_sources.json.gz", page_rows)
    write_object(
        pages / "manifest.json",
        dict(outputs={"page_sources.json.gz": digest(pages / "page_sources.json.gz")}),
    )
    write_array(
        links / "title_mapping.json.gz", [dict(target_title="Event", qid="Q99")]
    )
    write_object(
        links / "native_metadata.json",
        {"Q99": dict(id="Q99", label="Event", direct_types=["Q1190554"])},
    )
    write_object(links / "native_evidence.json", {})
    write_object(
        links / "manifest.json",
        dict(
            outputs={p.name: digest(p) for p in links.iterdir()},
            source_pages_sha256=digest(pages / "page_sources.json.gz"),
        ),
    )
    parameters = hierarchy / "parameters"
    parameters.mkdir()
    (parameters / "event_types.csv").write_text(
        "subtype_qid\nQ1190554\n", encoding="utf-8"
    )
    write_object(
        hierarchy / "recognition_approval.json",
        dict(
            status="RECOGNITION_RULE_ACCEPTED",
            root_qid="Q1190554",
            parameter_hashes={
                "event_types.csv": digest(parameters / "event_types.csv")
            },
        ),
    )
    model, graph, release = (tmp_path / name for name in ["model", "graph", "release"])
    assemble(prepared, pages, links, hierarchy, model)
    build_graph(model, graph)
    checked = subprocess.run(
        [
            str(python),
            "-m",
            "geo_agent.verify_compact",
            str(graph / "agent_graph.json.gz"),
            str(graph / "agent_acceptance.json"),
        ],
        cwd=ROOT / "Agent",
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr
    result = verify_and_package(prepared, model, graph, release)
    assert result["stage"] == "CORE_RELEASE_GEOGRAPHY_PENDING"
    assert result["relation_count"] == 3 and result["directed_view_count"] == 6
    assert result["geography_verification"]["locations"] == 1
    assert (release / "model/memberships.parquet").is_file()
    assert (release / "agent_adapter/geo_agent/compact_store.py").is_file()
    assert not (release / "agent/agent_graph.json.gz.sqlite.json").exists()
    assert (
        read_json(release / "agent_contract.json")["complete_pair_population"] is True
    )
    for name, sha in result["outputs"].items():
        assert digest(release / name) == sha
    with pytest.raises(FileExistsError):
        verify_and_package(prepared, model, graph, release)

    # A valid pair population must not conceal a changed entity name.
    from Agent.geo_agent.compact_format import records, write_graph

    reader = records(graph / "agent_graph.json.gz")
    _, metadata = next(reader)
    nodes = [next(reader)[1] for _ in range(metadata["node_count"])]
    pairs = [row for kind, row in reader]
    nodes[0]["name"] = "Wrong exact entity name"
    damaged = tmp_path / "damaged_graph"
    damaged.mkdir()
    write_graph(damaged / "agent_graph.json.gz", metadata, nodes, pairs)
    for name in ["relations.json.gz", "relations_schema.json"]:
        shutil.copyfile(graph / name, damaged / name)
    manifest = read_json(graph / "manifest.json")
    manifest["outputs"]["agent_graph.json.gz"] = digest(damaged / "agent_graph.json.gz")
    write_object(damaged / "manifest.json", manifest)
    acceptance = read_json(graph / "agent_acceptance.json")
    acceptance["graph_sha256"] = digest(damaged / "agent_graph.json.gz")
    write_object(damaged / "agent_acceptance.json", acceptance)
    with pytest.raises(ValueError, match="Graph node differs"):
        verify_and_package(prepared, model, damaged, tmp_path / "damaged_release")

    damaged_model = tmp_path / "damaged_model"
    shutil.copytree(model, damaged_model)
    binary = pq.read_table(damaged_model / "memberships.parquet").to_pylist()
    binary[0]["page_index"] += 99
    pq.write_table(pa.Table.from_pylist(binary), damaged_model / "memberships.parquet")
    manifest = read_json(damaged_model / "manifest.json")
    manifest["outputs"]["memberships.parquet"] = digest(
        damaged_model / "memberships.parquet"
    )
    (damaged_model / "manifest.json").write_text(__import__("json").dumps(manifest))
    from GG_Data.pipeline.simplified_verify import verify_population

    with pytest.raises(ValueError, match="Binary memberships differ"):
        verify_population(prepared, damaged_model)

    from GG_Data.pipeline.simplified_geography import (
        aggregate_geography,
        populate_geography,
    )

    geo_work = tmp_path / "geography_work"
    (geo_work / "geography_inputs").mkdir(parents=True)
    location = next(
        r for r in read_json(model / "entities.json.gz") if r["type"] == "LOC"
    )
    target = dict(place_id=location["entity_id"], name=location["name"])
    write_object(geo_work / "geography_inputs/report.json", dict(all_loc_targets=1))
    write_object(geo_work / "geography_inputs/targets.json", [target])
    write_object(geo_work / "geography_inputs/failed_inputs.json", [])
    ranking = geo_work / "batches/000000/ranking"
    (ranking / "sources").mkdir(parents=True)
    receipt = ranking / "sources/native.json"
    geometry = dict(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]])
    write_object(receipt, dict(response=[geometry]))
    chosen = dict(
        geometry=geometry,
        receipt=str(receipt.resolve()),
        source="OpenStreetMap",
        total=75,
    )
    write_object(
        ranking / "audit.json",
        dict(results=[dict(input=target, proposed=chosen, ranking=[chosen])]),
    )
    write_object(
        ranking / "verification.json",
        dict(
            status="VERIFIED_RANKING_PROPOSALS",
            inputs=1,
            outputs={
                "audit.json": digest(ranking / "audit.json"),
                "sources/native.json": digest(receipt),
            },
        ),
    )
    geography = tmp_path / "geography.json.gz"
    aggregate_geography(geo_work, geography)
    enriched_model, enriched_graph = (
        tmp_path / "enriched_model",
        tmp_path / "enriched_graph",
    )
    populate_geography(
        model, graph / "agent_graph.json.gz", geography, enriched_model, enriched_graph
    )
    checked = subprocess.run(
        [
            str(python),
            "-m",
            "geo_agent.verify_compact",
            str(enriched_graph / "agent_graph.json.gz"),
            str(enriched_graph / "agent_acceptance.json"),
        ],
        cwd=ROOT / "Agent",
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr
    geo_work.rename(tmp_path / "moved_source_work")
    enriched_release = tmp_path / "enriched_release"
    result = verify_and_package(
        prepared, enriched_model, enriched_graph, enriched_release
    )
    assert result["stage"] == "ENRICHED_RELEASE"
    assert result["geography_verification"]["evidence_bundle"]["status"] == "PASS"
    assert (
        result["geography_verification"]["spatial_checks"][0]["geometry_type"]
        == "Polygon"
    )

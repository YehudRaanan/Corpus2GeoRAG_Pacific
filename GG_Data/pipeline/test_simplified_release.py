"""Cross-environment smoke test of model -> real Agent -> portable release."""

import os
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

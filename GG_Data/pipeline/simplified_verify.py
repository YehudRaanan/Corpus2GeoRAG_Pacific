"""Independent full-population raw JSON and model integrity checks."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import shutil
import struct
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path

import ijson
import pyarrow.parquet as pq

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.simplified_agent import entity_id, write_array, write_object

LOG = logging.getLogger(__name__)


def verify_population(prepared: Path, model: Path) -> dict:
    manifest = read_json(model / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(model / name) != sha:
            raise ValueError(f"Changed model artifact: {name}")
    if digest(model / "mentions.json.gz") != digest(prepared / "mentions.json.gz"):
        raise ValueError("Original raw mentions changed")
    entities = read_json(model / "entities.json.gz")
    by_id = {r["entity_id"]: r for r in entities}
    original = read_json(prepared / "entities.json.gz")
    if len(by_id) != len(entities) or any(
        r["node_index"] != i
        or r["type"] == "DATE"
        or entity_id(r["name"], r["type"]) != r["entity_id"]
        for i, r in enumerate(entities)
    ):
        raise ValueError("Invalid full exact-key population")
    for row in original:
        saved = by_id.get(row["entity_id"], {})
        if any(saved.get(k) != row[k] for k in ["name", "type", "mention_count"]):
            raise ValueError("Original exact-key entity changed or disappeared")
    pages = read_json(model / "wiki_pages.json.gz")
    canonical = {p["page_index"]: p["canonical_page_index"] for p in pages}
    old_pages = read_json(prepared / "wiki_pages.json.gz")
    if {(p["page_index"], p["source_key"]) for p in pages} != {
        (p["page_index"], p["source_key"]) for p in old_pages
    }:
        raise ValueError("Source page scope changed")
    expected = {
        (m["entity_id"], canonical[m["page_index"]])
        for m in read_json(prepared / "memberships.json.gz")
    }
    qid_to_id = {}
    for event in read_json(model / "event_events.json.gz"):
        key = event["entity_id"]
        if key not in by_id or by_id[key]["type"] != "event":
            raise ValueError("Event foreign key failed")
        for native in event["native_records"]:
            qid_to_id[native["qid"]] = key
    statuses = Counter()
    for row in read_json(model / "event_recognition_audit.json.gz"):
        statuses[row["status"]] += 1
        if row["status"] == "EVENT":
            if row["qid"] not in qid_to_id or not row["recognized_types"]:
                raise ValueError("Recognized page event missing from population")
            expected.add((qid_to_id[row["qid"]], canonical[row["page_index"]]))
    memberships = read_json(model / "memberships.json.gz")
    actual = {(m["entity_id"], m["page_index"]) for m in memberships}
    if (
        actual != expected
        or len(actual) != len(memberships)
        or any(
            by_id[m["entity_id"]]["node_index"] != m["node_index"] for m in memberships
        )
    ):
        raise ValueError(
            "Full membership population differs from original and page events"
        )
    entity_counts = Counter(k for k, _ in actual)
    if any(r["page_count"] != entity_counts[r["entity_id"]] for r in entities):
        raise ValueError("Full entity denominator differs from membership")
    page_sizes = Counter(p for _, p in actual)
    return dict(
        status="PASS",
        exact_original_entities=len(original),
        entities=len(entities),
        events=sum(r["type"] == "event" for r in entities),
        memberships=len(actual),
        event_recognition_statuses=dict(statuses),
        raw_shared_page_count_sum=sum(c * (c - 1) // 2 for c in page_sizes.values()),
        source_revision_status="DANIEL_EXACT_REVISION_UNKNOWN",
    )


def verify_geography(model: Path, acceptance: dict) -> dict:
    """Independently compare all model LOC shapes/statuses to the loaded Agent."""
    places = {
        r["entity_id"]
        for r in read_json(model / "entities.json.gz")
        if r["type"] == "LOC"
    }
    rows = read_json(model / "geography.json.gz")
    by_id = {r["place_id"]: r for r in rows}
    if len(rows) != len(places) or set(by_id) != places:
        raise ValueError("Geography does not account for every exact LOC key")
    status = read_json(model / "manifest.json").get(
        "geography_status", "PENDING_LAST_STAGE"
    )
    if acceptance["geography_status"] != status:
        raise ValueError("Agent and model Geography stage differ")
    row_sha = hashlib.sha256()
    for key, row in sorted(by_id.items()):
        if status.startswith("COMPLETE") and (
            "PENDING" in row["status"] or not row["status"]
        ):
            raise ValueError("Geography still contains pending targets")
        row_sha.update(
            json.dumps(
                [key, row.get("geometry"), row["status"]],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        )
    checked = acceptance["geography"]
    if (
        checked["locations"] != len(places)
        or checked["geometry_rows_sha256"] != row_sha.hexdigest()
    ):
        raise ValueError("Agent Geography differs from complete model Geography")
    return dict(
        status=status,
        locations=len(places),
        status_counts=dict(Counter(r["status"] for r in rows)),
        geometry_rows_sha256=row_sha.hexdigest(),
        spatial_checks=checked["spatial_checks"],
    )


def verify_and_package(prepared: Path, model: Path, graph: Path, output: Path) -> dict:
    """Publish immutable JSON files only after full model and Agent checks pass."""
    if output.exists():
        raise FileExistsError(output)
    population = verify_population(prepared, model)
    graph_manifest = read_json(graph / "manifest.json")
    for name, sha in graph_manifest["outputs"].items():
        if digest(graph / name) != sha:
            raise ValueError(f"Changed graph artifact: {name}")
    acceptance = read_json(graph / "agent_acceptance.json")
    geography = verify_geography(model, acceptance)
    agent_root = Path(__file__).resolve().parents[2] / "Agent"
    code_paths = sorted((agent_root / "geo_agent").glob("*.py"))
    if {p.name: digest(p) for p in code_paths} != acceptance["agent_code_sha256"]:
        raise ValueError("Agent adapter differs from the fully verified code")
    raw_report = read_json(prepared.parent / "raw_verification.json")
    if (
        acceptance["status"] != "PASS"
        or acceptance["graph_sha256"] != digest(graph / "agent_graph.json.gz")
        or acceptance["node_count"] != population["entities"]
        or acceptance["coverage"]["raw_shared_page_count_sum"]
        != population["raw_shared_page_count_sum"]
        or graph_manifest["model_manifest_sha256"] != digest(model / "manifest.json")
        or raw_report["status"] != "PASS"
        or raw_report["prepared_manifest_sha256"] != digest(prepared / "manifest.json")
    ):
        raise ValueError("Acceptance reports do not match this complete population")
    rows_sha = hashlib.sha256()
    count = 0
    with gzip.open(graph / "relations.json.gz", "rb") as stream:
        for row in ijson.items(stream, "item", use_float=True):
            rows_sha.update(struct.pack("<qqqdd", *row))
            count += 1
            if count % 10000000 == 0:
                LOG.info("Relations JSON rows compared %s", count)
    if (
        count != acceptance["coverage"]["pair_count"]
        or rows_sha.hexdigest() != acceptance["coverage"]["pair_rows_sha256"]
    ):
        raise ValueError("Relations JSON differs from the fully verified Agent graph")
    output.mkdir()
    for folder, destination in [(model, "model"), (graph, "agent")]:
        target = output / destination
        target.mkdir()
        for path in folder.iterdir():
            if (
                path.is_file()
                and not path.name.endswith(".sqlite.json")
                and (
                    destination == "model"
                    or path.name.endswith(".json")
                    or path.name.endswith(".json.gz")
                )
            ):
                os.link(path, target / path.name)
    os.link(prepared.parent / "raw_verification.json", output / "raw_verification.json")
    adapter = output / "agent_adapter"
    (adapter / "geo_agent").mkdir(parents=True)
    for path in code_paths:
        # Copy code: later development must not mutate the release via a hard link.
        shutil.copyfile(path, adapter / "geo_agent" / path.name)
    for name in ["pyproject.toml", "README.md"]:
        shutil.copyfile(agent_root / name, adapter / name)
    write_object(
        output / "agent_contract.json",
        dict(
            format="simplified-cooccurrence-v1",
            graph="agent/agent_graph.json.gz",
            adapter="agent_adapter/geo_agent",
            loader="geo_agent.graph_store.GraphStore.from_json",
            edge_columns=[
                "source_index",
                "target_index",
                "shared_page_count",
                "strength_source_target",
                "strength_target_source",
            ],
            entity_index="model/entities.json.gz node_index",
            complete_pair_population=True,
            derived_index="Read-only SQLite index is built locally on first load; it is not required for interchange",
            edge_count_semantics="Integer shared-page count; fractional weights use each endpoint's distinct-page denominator",
            relation_semantics="PAGE_CO_OCCURRENCE_ONLY",
            geography_status=geography["status"],
            source_revision_status="DANIEL_EXACT_REVISION_UNKNOWN",
            llm_invoked=False,
            agent_code_sha256=acceptance["agent_code_sha256"],
        ),
    )
    provenance = output / "provenance"
    provenance.mkdir()
    for folder_name, names in [
        ("page_acquisition", ["page_sources.json.gz", "manifest.json"]),
        (
            "page_link_metadata",
            [
                "title_mapping.json.gz",
                "native_metadata.json",
                "native_evidence.json",
                "manifest.json",
            ],
        ),
    ]:
        source_dir = prepared.parent / folder_name
        target_dir = provenance / folder_name
        target_dir.mkdir()
        for name in names:
            os.link(source_dir / name, target_dir / name)

    def raw_pages():
        for page in read_json(
            prepared.parent / "page_acquisition/page_sources.json.gz"
        ):
            path = Path(page["raw_path"])
            if digest(path) != page["raw_sha256"]:
                raise ValueError("Source revision raw evidence changed")
            yield dict(
                page_index=page["page_index"],
                revision_id=page["revision_id"],
                raw_sha256=page["raw_sha256"],
                raw_wikitext=path.read_text(encoding="utf-8"),
            )

    write_array(provenance / "raw_page_revisions.json.gz", raw_pages())
    write_object(
        provenance / "event_recognition_rule.json",
        [
            dict(
                path=r["path"],
                sha256=r["sha256"],
                content=Path(r["path"]).read_text(encoding="utf-8"),
            )
            for r in read_json(model / "manifest.json")["event_rule"]
        ],
    )
    result = dict(
        stage=(
            "ENRICHED_RELEASE"
            if geography["status"].startswith("COMPLETE")
            else "CORE_RELEASE_GEOGRAPHY_PENDING"
        ),
        population_verification=population,
        raw_verification=raw_report,
        agent_graph="agent/agent_graph.json.gz",
        relation_count=count,
        directed_view_count=2 * count,
        geography_status=geography["status"],
        geography_verification=geography,
        relation_rule="shared_page_count / distinct_pages_containing_source",
        exclusions=[
            "DATE entities",
            "entity identity matching",
            "factual native relations",
        ],
        outputs={
            p.relative_to(output).as_posix(): digest(p)
            for p in output.rglob("*")
            if p.is_file()
        },
    )
    write_object(output / "manifest.json", result)
    return result


def verify_raw_rows(prepared: Path):
    manifest = read_json(prepared / "manifest.json")
    for name in ["entities.json.gz", "wiki_pages.json.gz", "mentions.json.gz"]:
        if digest(prepared / name) != manifest["outputs"][name]:
            raise ValueError(f"Changed artifact: {name}")
    source = Path(manifest["input"]["path"])
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Pinned input hash changed")
    entities = read_json(prepared / "entities.json.gz")
    by_key = {(r["name"], r["type"]): r for r in entities}
    if len(by_key) != len(entities) or any(
        k[1] == "DATE" or entity_id(*k) != r["entity_id"] for k, r in by_key.items()
    ):
        raise ValueError("Invalid exact identity population")
    pages = {
        r["source_key"]: r["page_index"]
        for r in read_json(prepared / "wiki_pages.json.gz")
    }
    appearances = defaultdict(set)
    mentions = Counter()
    parquet = pq.ParquetFile(source)
    originals = (
        r for batch in parquet.iter_batches(batch_size=8192) for r in batch.to_pylist()
    )
    total = dates = 0
    with gzip.open(prepared / "mentions.json.gz", "rb") as stream:
        for index, (raw, saved) in enumerate(
            zip_longest(originals, ijson.items(stream, "item", use_float=True))
        ):
            if (
                raw is None
                or saved is None
                or saved["raw"] != raw
                or saved["source_row_index"] != index
                or saved["mention_id"] != f"mention:{index}"
                or saved["page_index"] != pages[raw["Source"]]
            ):
                raise ValueError(f"Raw row differs at {index}")
            excluded = raw["entity_group"] == "DATE"
            key = (raw["word"], raw["entity_group"])
            expected = None if excluded else by_key[key]["entity_id"]
            if saved["entity_id"] != expected or saved["exclusion_reason"] != (
                "DATE_EXCLUDED" if excluded else None
            ):
                raise ValueError(f"Identity/exclusion differs at {index}")
            dates += int(excluded)
            total += 1
            if not excluded:
                mentions[key] += 1
                appearances[key].add(pages[raw["Source"]])
            if total % 262144 == 0:
                LOG.info(
                    "Independently verified raw rows %s/%s",
                    total,
                    parquet.metadata.num_rows,
                )
    if (
        total != parquet.metadata.num_rows
        or dates != manifest["counts"]["excluded_date_rows"]
        or set(mentions) != set(by_key)
    ):
        raise ValueError("Raw population accounting failed")
    for key, row in by_key.items():
        if (
            row["page_count"] != len(appearances[key])
            or row["mention_count"] != mentions[key]
        ):
            raise ValueError("Entity count differs from original rows")
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Input changed during verification")
    return dict(
        status="PASS",
        raw_rows_verified=total,
        date_rows_verified=dates,
        exact_entities_verified=len(entities),
        distinct_memberships_verified=sum(map(len, appearances.values())),
        input_sha256=manifest["input"]["sha256"],
        prepared_manifest_sha256=digest(prepared / "manifest.json"),
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--release", type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        raise FileExistsError(args.report)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.release:
        if args.model is None or args.graph is None:
            parser.error("--release requires --model and --graph")
        result = verify_and_package(args.prepared, args.model, args.graph, args.release)
    else:
        if args.report is None:
            parser.error("Raw replay requires --report")
        result = verify_raw_rows(args.prepared)
        write_object(args.report, result)
    LOG.info("Finished: %s", result)


if __name__ == "__main__":
    main()

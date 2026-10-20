"""Populate existing Entities using snapshot-first Wikidata records (S2T 1/6).

The latest 20 October rule replaces archive comparison and per-case exceptions.
Do not generate version-difference reports, rematch or reclassify mentions.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from pathlib import Path

from GG_Data.pipeline.entities import acquire_missing, native_record, populate
from GG_Data.pipeline.poc import ROOT, digest, read_json


def run(audit: Path, cache: Path, store: Path, output: Path) -> dict:
    for path in (store, output):
        if not path.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs"):
            raise ValueError("Use the approved D: pipeline outputs directory")
    if output.exists():
        raise ValueError("Use a new source-selection output directory")
    manifest_path = audit / "manifest.json"
    manifest = read_json(manifest_path)
    verification = read_json(audit / "verification.json")
    if (
        verification["status"] != "VERIFIED_BQ_COVERAGE_MARKERS_ONLY"
        or digest(manifest_path) != verification["manifest_sha256"]
    ):
        raise ValueError("Expected verified BQ coverage audit")
    for name, expected in manifest["outputs"].items():
        if digest(audit / name) != expected:
            raise ValueError(f"Audit output differs: {name}")
    reference_path = cache / "reference_manifest.json"
    if digest(reference_path) != manifest["inputs"][str(reference_path)]:
        raise ValueError("Reference manifest differs from the coverage audit")
    reference = read_json(reference_path)
    if reference["table_snapshot"]["snapshot_at"] != manifest["snapshot_at"]:
        raise ValueError("Snapshot differs from the coverage audit")
    entities = read_json(audit / "entities.json.gz")
    qids = set(manifest["existing_non_bq_full_record_qids"])
    records, provenance, metadata, available = {}, {}, {}, {}
    for row in entities:
        qid = row["entity_id"]
        if not qid.startswith("Q"):
            continue
        envelope = row["raw_reference"]["full"]
        native_record(envelope, qid)
        if qid in metadata and metadata[qid] != row["raw_reference"]["matching"]:
            raise ValueError(f"Typed rows disagree on saved matching evidence: {qid}")
        metadata[qid] = row["raw_reference"]["matching"]
        if qid in qids:
            available.setdefault(qid, []).append((envelope, row["sources"][0]))
        else:
            source = row["sources"][0]
            if (
                source["provider"] != "BIGQUERY"
                or source["snapshot_at"] != manifest["snapshot_at"]
            ):
                raise ValueError(f"Unverified snapshot record: {qid}")
            records[qid], provenance[qid] = envelope, source
    if available.keys() != qids:
        raise ValueError("Requested population differs from the coverage audit")
    # Reuse the cached exact query. Only absent snapshot records can use a
    # complete available same-QID version; do not fall back on service errors.
    acquired, sources = acquire_missing(
        qids, store, reference, available_records=available
    )
    records.update(acquired)
    provenance.update(sources)
    step1 = ROOT / "GG_Data/pipeline/outputs/poc_10k"
    first = read_json(step1 / "manifest.json")
    for name, sha in first["outputs"].items():
        if digest(step1 / name) != sha:
            raise ValueError(f"Preserved input differs: {name}")
    if digest(cache / "manifest.json") != first["resolution_run_id"]:
        raise ValueError("Matching run differs from preserved input")
    rows = populate(
        read_json(step1 / "mentions.json.gz"),
        records,
        metadata,
        provenance,
    )
    old = {(r["entity_id"], r["type"]): r for r in entities}
    if {(r["entity_id"], r["type"]) for r in rows} != old.keys():
        raise ValueError("Entity IDs or saved broad types changed")
    result_rows = []
    for row in rows:
        prior = old[row["entity_id"], row["type"]]
        if row["entity_id"].startswith("SYN_"):
            result_rows.append(prior)  # Synthetic identity and evidence are untouched.
            continue
        # Refresh only source-derived fields. All user/model enrichment and
        # original matching/type decisions remain as previously populated.
        updated = {**prior, **row, "importance": prior["importance"]}
        for name in ("text", "embedding", "review_status", "direct_types", "parents"):
            updated[name] = prior[name]
        updated["attributes"] = {**prior["attributes"], **row["attributes"]}
        updated["attributes"]["bq_availability"] = {
            **prior["attributes"]["bq_availability"],
            "full_record_alignment_verified": provenance[row["entity_id"]]["provider"]
            == "BIGQUERY",
        }
        result_rows.append(updated)
    output.mkdir(parents=True)
    for name, value in (("entities", result_rows), ("full_records", records)):
        with gzip.open(output / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
    snapshot_count = sum(s["provider"] == "BIGQUERY" for s in provenance.values())
    result = dict(
        status="ENTITIES_SNAPSHOT_FIRST",
        snapshot_at=manifest["snapshot_at"],
        requested_qids=len(qids),
        acquired_qids=len(acquired),
        entity_count=len(result_rows),
        qid_count=len(records),
        snapshot_qids=snapshot_count,
        fallback_qids=len(records) - snapshot_count,
        source_rule="AGREED_SNAPSHOT_THEN_LATEST_AVAILABLE_SAME_QID",
        provenance=provenance,
        inputs={
            str(p): digest(p)
            for p in (
                manifest_path,
                reference_path,
                step1 / "manifest.json",
                step1 / "mentions.json.gz",
            )
        },
        code_sha256={
            p.name: digest(p)
            for p in (Path(__file__), Path(__file__).with_name("entities.py"))
        },
        outputs={p.name: digest(p) for p in output.glob("*.json.gz")},
        model_updated=True,
        matching_changed=False,
        pending_stages=["Events", "Relations rebuild", "Geography", "graph", "Agent"],
    )
    (output / "manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("audit", "cache", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run(args.audit, args.cache, args.store, args.output)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"provenance", "inputs", "outputs", "code_sha256"}
            }
        )
    )

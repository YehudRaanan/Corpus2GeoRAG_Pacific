"""Acquire archived POC identities from the version's pinned BQ snapshot.

Population S2T section 1: this is reference acquisition only. Never overwrite
model rows or use current Wikidata as a fallback. Stop at the first changed
EN/JA label or P31/P279 evidence for discussion under the POC stop rule.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from pathlib import Path

from GG_Data.pipeline.entities import acquire_missing, native_record
from GG_Data.pipeline.poc import ROOT, digest, read_json


def first_difference(old: dict, pinned: dict) -> dict | None:
    """Compare identity evidence without selecting a name or inferring a type."""
    for language in ("en", "ja"):
        before = old.get("labels", {}).get(language)
        after = pinned.get("labels", {}).get(language)
        if before != after:
            return dict(field=f"labels.{language}", archived=before, pinned=after)
    for property_id in ("P31", "P279"):
        before = old.get("claims", {}).get(property_id, [])
        after = pinned.get("claims", {}).get(property_id, [])
        if before != after:
            return dict(field=f"claims.{property_id}", archived=before, pinned=after)
    return None


def run(audit: Path, cache: Path, store: Path, output: Path) -> dict:
    for path in (store, output):
        if not path.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs"):
            raise ValueError("Use the approved D: pipeline outputs directory")
    if output.exists():
        raise ValueError("Use a new alignment output directory")
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
    archived = {}
    for row in entities:
        if row["entity_id"] in qids:
            old = native_record(row["raw_reference"]["full"], row["entity_id"])
            if row["entity_id"] in archived and archived[row["entity_id"]] != old:
                raise ValueError("Typed rows disagree on the original full record")
            archived[row["entity_id"]] = old
    if archived.keys() != qids:
        raise ValueError("Archive population differs from the coverage audit")
    # Existing adapter preserves SQL, dry run, job receipt and complete result.
    # A source failure stops here; there is no retry or source substitution.
    records, provenance = acquire_missing(qids, store, reference)
    output.mkdir(parents=True)
    records_path = output / "full_records.json.gz"
    with gzip.open(records_path, "wt", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, allow_nan=False)
    conflict = None
    checked = 0
    for qid in sorted(qids):
        pinned = native_record(records[qid], qid)
        checked += 1
        difference = first_difference(archived[qid], pinned)
        if difference:
            conflict = dict(qid=qid, **difference)
            break  # No model population or further comparisons after a surprise.
    result = dict(
        status=(
            "STOPPED_IDENTITY_EVIDENCE_DIFFERENCE" if conflict else "REFERENCE_ACQUIRED"
        ),
        snapshot_at=manifest["snapshot_at"],
        requested_qids=len(qids),
        acquired_qids=len(records),
        compared_qids=checked,
        first_difference=conflict,
        provenance=provenance,
        inputs={str(p): digest(p) for p in (manifest_path, reference_path)},
        code_sha256=digest(Path(__file__)),
        outputs={records_path.name: digest(records_path)},
        model_updated=False,
        event_stage_status=manifest["event_stage_status"],
    )
    (output / "manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run(args.audit, args.cache, args.store, args.output)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"provenance", "inputs", "outputs"}
            },
            ensure_ascii=False,
        )
    )

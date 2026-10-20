"""Acquire archived POC identities from the version's pinned BQ snapshot.

Population S2T section 1: this is reference acquisition only. Never overwrite
model rows or use current Wikidata as a fallback. Stop at the first changed
EN/JA label or P31/P279 evidence for discussion under the POC stop rule.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
from pathlib import Path

from GG_Data.pipeline.entities import acquire_missing, native_record
from GG_Data.pipeline.poc import ROOT, digest, read_json

# Exact evidence approved from the first alignment report, not a general
# permission to accept other classification changes in this or future versions.
APPROVED_Q1014037_P31 = (
    "628ae776cc33be2c9fc797c41c62fc0a41cbb3d82a84d4d0a3570e498f48f988",
    "91f5224ba4375dd84ef18453e019870bd573fe8d0da9c17f8189550a4973d655",
)


def without_snak_checksums(value: object) -> object:
    """Compare API/dump formats; preserve reference hashes and all fact values."""
    if isinstance(value, list):
        return [without_snak_checksums(v) for v in value]
    if isinstance(value, dict):
        return {
            k: without_snak_checksums(v)
            for k, v in value.items()
            if not (k == "hash" and "snaktype" in value and "property" in value)
        }
    return value


def first_difference(old: dict, pinned: dict, *, qid: str | None = None) -> dict | None:
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
            # API/cache formats can omit the optional snak checksum. It is
            # not a class, statement ID, rank, qualifier or reference value.
            comparable = [without_snak_checksums(claims) for claims in (before, after)]
            if comparable[0] == comparable[1]:
                continue
            # S2T 1, user approval 20 October: only this exact source change
            # is accepted. Keep the QID and MISC type; no type inference here.
            # Hash the complete claims so a new rank/qualifier change still stops.
            if qid == "Q1014037" and property_id == "P31":
                fingerprints = tuple(
                    hashlib.sha256(
                        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
                    ).hexdigest()
                    for value in (before, after)
                )
                if fingerprints == APPROVED_Q1014037_P31:
                    continue
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
        difference = first_difference(archived[qid], pinned, qid=qid)
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
        approved_case=dict(
            qid="Q1014037",
            field="claims.P31",
            use="PINNED_BQ_EVIDENCE",
            keep_entity_id=True,
            keep_type="MISC",
        ),
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

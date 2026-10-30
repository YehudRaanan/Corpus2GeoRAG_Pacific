"""Filter saved QID support and share conservative native-P31/P279 compatibility.

No lookup is performed. Missing source or ancestry evidence stays eligible;
only source evidence proved entirely excluded removes an inventory row.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from GG_Data.entity_resolution.hundred_page_pilot.filter_source_content import (
    classify_span,
    source_intervals,
)
from GG_Data.entity_resolution.luke_pilot.data import sha256

POLICY_VERSION = "qid-source-native-types-v1"
# Read the existing constant without importing its CLI and optional dependencies.
TYPE_ROOTS = next(
    ast.literal_eval(node.value)
    for node in ast.parse(
        (Path(__file__).parents[1] / "bilingual_page_pilot.py").read_text(
            encoding="utf-8"
        )
    ).body
    if isinstance(node, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == "TYPE_ROOTS" for t in node.targets)
)


def source_allowed(entity: dict) -> bool:
    """Known excluded source support cannot re-enter through another caller."""
    return entity.get("qid_source_status") != "EXCLUDE"


def compatible(entity: dict, mention_type: str) -> bool:
    """Keep legacy callers unchanged; enriched rows defer DATE and unknown types."""
    if not source_allowed(entity):
        return False
    if "type_categories" not in entity and "type_unknown" not in entity:
        return True
    if mention_type == "DATE":
        return False
    return (
        mention_type == "MISC"
        or bool(entity.get("type_unknown", True))
        or mention_type in (entity.get("type_categories") or [])
    )


def _types(native_types: list[str], metadata: dict) -> dict:
    todo, visited, missing = list(native_types), set(), set()
    while todo:
        qid = todo.pop()
        if qid in visited:
            continue
        visited.add(qid)
        record = metadata.get(qid)
        if (
            not isinstance(record, dict)
            or record.get("missing") is True
            or not isinstance(record.get("parents"), list)
        ):
            missing.add(qid)
        else:
            todo.extend(record["parents"])
    return dict(
        type_categories=sorted(k for k, roots in TYPE_ROOTS.items() if visited & roots),
        type_unknown=not native_types or bool(missing),
        type_missing_classes=sorted(missing),
    )


def filter_inventory(
    entities: list[dict], evidence: list[dict], raw_root: Path, type_metadata: dict
) -> tuple[list[dict], list[dict]]:
    """Return retained rows and one source/type ledger row per input scope/QID."""
    keys = [(r["page_id"], r["revision_id"], r["qid"]) for r in entities]
    if len(keys) != len(set(keys)):
        raise ValueError("Inventory requires unique page/revision/QID rows")
    if any("qid_filter_policy_version" in row for row in entities):
        raise ValueError("Inventory already has QID filter annotations")
    indexed = defaultdict(list)
    for row in evidence:
        if row.get("qid"):
            indexed[row.get("page_id"), row.get("revision_id"), row["qid"]].append(row)
    raw_root = raw_root.resolve()
    raw_cache, type_cache = {}, {}

    def classify(row: dict) -> dict:
        result = dict(
            origin=row.get("link_origin"),
            target_title=row.get("target_title"),
            raw_path=row.get("raw_evidence_path"),
            raw_sha256=row.get("raw_sha256"),
            status="UNKNOWN",
            reason="missing_raw_evidence",
            start=None,
            end=None,
            raw_verified=False,
        )
        if not result["raw_path"] or not result["raw_sha256"]:
            return result
        path = Path(result["raw_path"])
        if not path.is_absolute():
            path = raw_root / path
        path = path.resolve()
        if not path.is_relative_to(raw_root):
            raise ValueError(f"Raw evidence outside raw root: {path}")
        if not path.exists():
            return result
        if path not in raw_cache:
            raw_bytes = path.read_bytes()
            raw = raw_bytes.decode("utf-8")
            raw_cache[path] = (
                raw,
                hashlib.sha256(raw_bytes).hexdigest(),
                *source_intervals(raw),
            )
        raw, digest, spans, headings = raw_cache[path]
        if digest != result["raw_sha256"]:
            raise ValueError(f"Raw revision hash mismatch: {path}")
        result["raw_verified"] = True
        if result["origin"] == "PAGE_OWN_QID":
            verified = row.get("page_own_qid_page_id_verified") is True
            result.update(
                status="KEEP" if verified else "UNKNOWN",
                reason=(
                    "verified_page_own_qid" if verified else "unverified_page_own_qid"
                ),
            )
            return result
        if row.get("name_start") is not None:
            left, right, text = row["name_start"], row.get("name_end"), row.get("name")
        else:
            left, right, text = (
                row.get("anchor_start"),
                row.get("anchor_end"),
                row.get("anchor_text"),
            )
        if left is None or right is None:
            result["reason"] = "missing_visible_offsets"
            return result
        if (
            type(left) is not int
            or type(right) is not int
            or not 0 <= left < right <= len(raw)
        ):
            raise ValueError(f"Invalid source offsets: {path}: {left}/{right}")
        if text is not None and raw[left:right] != text:
            raise ValueError(f"Source anchor text mismatch: {path}: {left}/{right}")
        start, end = row.get("raw_start"), row.get("raw_end")
        if start is not None or end is not None:
            if (
                type(start) is not int
                or type(end) is not int
                or not 0 <= start <= left < right <= end <= len(raw)
            ):
                raise ValueError(
                    f"Invalid raw construct offsets: {path}: {start}/{end}"
                )
            if row.get("raw_text") is not None and raw[start:end] != row["raw_text"]:
                raise ValueError(f"Raw construct text mismatch: {path}: {start}/{end}")
        classified = classify_span(left, right, spans, headings)
        result.update(
            start=left,
            end=right,
            status=classified["status"],
            reason=classified["reason"],
        )
        return result

    retained, audit = [], []
    for entity, key in zip(entities, keys):
        supports, seen = [], set()
        for row in indexed[key]:
            support = classify(row)
            identity = tuple(support.values())
            if identity not in seen:
                supports.append(support)
                seen.add(identity)
        counts = Counter(s["status"] for s in supports)
        direct = sum(s["origin"] == "RAW_DIRECT_LINK" for s in supports)
        missing = []
        if not supports:
            missing.append("no_recorded_support")
        if direct < (entity.get("raw_link_occurrences") or 0):
            missing.append("missing_recorded_direct_occurrences")
        expected_origins = set(entity.get("link_origin") or [])
        if expected_origins - {s["origin"] for s in supports}:
            missing.append("missing_recorded_link_origins")
        expected_titles = set(entity.get("linked_titles") or [])
        if expected_titles - {s["target_title"] for s in supports}:
            missing.append("missing_recorded_link_targets")
        if counts["KEEP"]:
            status = "KEEP"
        elif counts["REVIEW"]:
            status = "REVIEW_KEEP"
        elif missing or counts["UNKNOWN"]:
            status = "UNKNOWN_KEEP"
        else:
            status = "EXCLUDE"
        native = tuple(entity.get("native_types") or [])
        if native not in type_cache:
            type_cache[native] = _types(list(native), type_metadata)
        types = type_cache[native]
        annotated = dict(
            entity,
            qid_source_status=status,
            type_categories=types["type_categories"],
            type_unknown=types["type_unknown"],
            qid_filter_policy_version=POLICY_VERSION,
        )
        if source_allowed(annotated):
            retained.append(annotated)
        audit.append(
            dict(
                page_id=key[0],
                revision_id=key[1],
                qid=key[2],
                qid_source_status=status,
                qid_filter_policy_version=POLICY_VERSION,
                **types,
                native_types=list(native),
                source_support_counts=dict(counts),
                source_support=supports,
                source_incomplete_reasons=missing,
                page_own_verified=sum(
                    s["reason"] == "verified_page_own_qid" for s in supports
                ),
            )
        )
    # Detect mutation during filtering before returning a trusted retained inventory.
    for path, (_, digest, _, _) in raw_cache.items():
        if sha256(path) != digest:
            raise ValueError(f"Raw revision changed during filtering: {path}")
    return retained, audit


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entities", required=True, type=Path)
    parser.add_argument(
        "--evidence", required=True, type=Path, nargs="+", action="append"
    )
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--type-metadata", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise FileExistsError(f"Preserve existing output: {args.out}")
    paths = [
        args.entities,
        *[p for batch in args.evidence for p in batch],
        args.type_metadata,
    ]
    input_hashes = {str(p.resolve()): sha256(p) for p in paths}
    opener = gzip.open if args.type_metadata.suffix == ".gz" else open
    with opener(args.type_metadata, "rt", encoding="utf-8") as stream:
        metadata = json.load(stream)
    original = pq.read_table(args.entities)
    evidence = [r for p in paths[1:-1] for r in pq.read_table(p).to_pylist()]
    retained, audit = filter_inventory(
        original.to_pylist(), evidence, args.raw_root, metadata
    )
    for path, digest in input_hashes.items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"Input changed during filtering: {path}")
    args.out.mkdir(parents=True, exist_ok=False)
    schema = pa.schema(
        [
            *original.schema,
            ("qid_source_status", pa.string()),
            ("type_categories", pa.list_(pa.string())),
            ("type_unknown", pa.bool_()),
            ("qid_filter_policy_version", pa.string()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(retained, schema=schema),
        args.out / "entities.parquet",
        compression="zstd",
    )
    audit_table = pa.Table.from_pylist(audit)
    if audit:
        audit_schema = pa.schema(
            [
                (
                    pa.field(f.name, pa.map_(pa.string(), pa.int64()))
                    if f.name == "source_support_counts"
                    else f
                )
                for f in audit_table.schema
            ]
        )
        audit_table = pa.Table.from_pylist(audit, schema=audit_schema)
    pq.write_table(audit_table, args.out / "audit.parquet", compression="zstd")
    native_columns = [
        n
        for n in original.column_names
        if n.startswith("metadata_")
        or n in {"page_id", "revision_id", "qid", "native_types", "p31_status"}
    ]
    pq.write_table(
        original.select(native_columns),
        args.out / "native_metadata_snapshot.parquet",
        compression="zstd",
    )
    snapshot = args.out / "type_metadata_snapshot.json.gz"
    if args.type_metadata.suffix == ".gz":
        shutil.copyfile(args.type_metadata, snapshot)
    else:
        with gzip.open(snapshot, "wt", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False)
    summary = dict(
        policy_version=POLICY_VERSION,
        input_rows=original.num_rows,
        retained_rows=len(retained),
        excluded_rows=len(audit) - len(retained),
        source_status_counts=dict(Counter(r["qid_source_status"] for r in audit)),
        page_own_verified=sum(r["page_own_verified"] for r in audit),
        type_unknown_rows=sum(r["type_unknown"] for r in audit),
        type_roots={k: sorted(v) for k, v in TYPE_ROOTS.items()},
        type_hierarchy_sha256=input_hashes[str(args.type_metadata.resolve())],
        native_metadata_snapshot_utc=sorted(
            {
                r.get("metadata_snapshot_utc")
                for r in original.to_pylist()
                if r.get("metadata_snapshot_utc")
            }
        ),
        input_sha256=input_hashes,
        raw_revision_sha256={
            s["raw_path"]: s["raw_sha256"]
            for r in audit
            for s in r["source_support"]
            if s["raw_verified"]
        },
        code_sha256={
            str(p.resolve()): sha256(p)
            for p in (
                Path(__file__),
                Path(__file__).with_name("filter_source_content.py"),
                Path(__file__).parents[1] / "bilingual_page_pilot.py",
            )
        },
    )
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    hashes = {p.name: sha256(p) for p in args.out.iterdir() if p.is_file()}
    (args.out / "hashes.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

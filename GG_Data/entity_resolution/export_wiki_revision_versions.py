"""Export two immutable versions from accepted decisions, without rematching text."""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from attach_source_page_ids import WikiClient, read_json, save_json, sha256

LOG = logging.getLogger(__name__)
FIELDS = {
    "wiki_page_title": pa.string(),
    "wiki_revision_id": pa.int64(),
    "wiki_revision_timestamp": pa.timestamp("us", tz="UTC"),
    "wiki_revision_url": pa.string(),
    "wiki_match_method": pa.string(),
    "wiki_match_status": pa.string(),
    "wiki_revision_evidence": pa.string(),
    "wiki_text_sha256": pa.string(),
    "wiki_baseline_status": pa.string(),
}


def verify_saved_evidence(directory: Path) -> int:
    """Check accepted evidence bytes before copying any prior attribution."""
    manifest = read_json(directory / "manifest.json")
    for name, digest in manifest["files_sha256"].items():
        if sha256(directory / name) != digest:
            raise ValueError(f"Saved evidence changed: {directory / name}")
    return len(manifest["files_sha256"])


def enrich(
    table: pa.Table,
    decisions: dict[tuple[str, str], dict[str, Any]],
    historical: dict[tuple[str, str], dict[str, Any]],
    revisions: dict[int, dict[str, Any]] | None = None,
) -> pa.Table:
    """Copy decisions to rows; never execute text matching or replace accepted IDs."""
    if any(name in table.column_names for name in FIELDS):
        raise ValueError("Input already contains version metadata")
    ids = table["wiki_page_id"].to_pylist()
    columns: dict[str, list[Any]] = {name: [] for name in FIELDS}
    for i, (source, text) in enumerate(
        zip(table["Source"].to_pylist(), table["Text"].to_pylist())
    ):
        decision = decisions[(source, text)]
        if ids[i] != decision["wiki_page_id"]:
            raise ValueError("Baseline table and accepted decision disagree")
        match = historical.get((source, text))
        metadata = {name: None for name in FIELDS}
        metadata.update(
            wiki_text_sha256=decision["text_sha256"],
            wiki_baseline_status=decision["status"],
            wiki_match_status=(
                "BASELINE_PAGE_ID_METADATA_PENDING"
                if ids[i] is not None
                else "UNRESOLVED_NOT_SEARCHED_IN_THIS_EXPORT"
            ),
        )
        if match:
            if ids[i] is not None:
                raise ValueError("Historical update targets an already assigned page")
            ids[i] = match["pageid"]
            metadata.update(
                wiki_page_title=match["title"],
                wiki_revision_id=match["revid"],
                wiki_revision_timestamp=datetime.fromisoformat(
                    match["timestamp"].replace("Z", "+00:00")
                ),
                wiki_revision_url=f"https://en.wikipedia.org/w/index.php?oldid={match['revid']}",
                wiki_match_method=match["status"],
                wiki_match_status="VERIFIED_HISTORICAL_SAVED_EVIDENCE",
                wiki_revision_evidence=match["parse_evidence"],
            )
        elif ids[i] is not None and revisions is not None:
            revision = revisions[decision["revision_id"]]
            if (
                revision["pageid"] != ids[i]
                or revision["revid"] != decision["revision_id"]
            ):
                raise ValueError("Saved revision/page identity mismatch")
            metadata.update(
                wiki_page_title=decision["canonical_title"],
                wiki_revision_id=revision["revid"],
                wiki_revision_timestamp=datetime.fromisoformat(
                    revision["timestamp"].replace("Z", "+00:00")
                ),
                wiki_revision_url=f"https://en.wikipedia.org/w/index.php?oldid={revision['revid']}",
                wiki_match_method=decision["status"],
                wiki_match_status="VERIFIED_BASELINE_SAVED_EVIDENCE",
                wiki_revision_evidence=json.dumps(
                    {
                        "page_evidence": decision["page_evidence"],
                        "revision_metadata": revision["evidence"],
                    },
                    sort_keys=True,
                ),
            )
        for name in columns:
            columns[name].append(metadata[name])
    enriched = table.set_column(
        table.schema.get_field_index("wiki_page_id"),
        "wiki_page_id",
        pa.array(ids, type=pa.int64()),
    )
    for name, dtype in FIELDS.items():
        enriched = enriched.append_column(name, pa.array(columns[name], type=dtype))
    return enriched


def write_new(table: pa.Table, target: Path) -> pa.Table:
    if target.exists() or target.with_suffix(".parquet.tmp").exists():
        raise FileExistsError(f"Preserve existing output: {target}")
    temporary = target.with_suffix(".parquet.tmp")
    pq.write_table(table, temporary, compression="zstd")
    restored = pq.read_table(temporary)
    if not restored.equals(table, check_metadata=True):
        raise ValueError("Export roundtrip changed values or metadata")
    temporary.rename(target)
    return restored


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    stem = "georag_selected_v2_full_n36335_r345732948_20261024"
    paths = [
        args.output / f"{stem}_v1_historical_recovery.parquet",
        args.output / f"{stem}_v2_revision_metadata.parquet",
    ]
    if any(path.exists() for path in paths):
        raise FileExistsError("Preserve existing staged Parquets")
    baseline = args.baseline / f"{stem}_with_wiki_page_id.parquet"
    original_hash = sha256(baseline)
    if (
        original_hash
        != "0b34290f0f74cc060dad325ca5fe32a9505acfe2ae84cca3dd0768ad2ec48cd1"
    ):
        raise ValueError("Unexpected baseline bytes")
    verify_saved_evidence(args.baseline)
    verify_saved_evidence(args.pilot)
    with gzip.open(
        args.baseline / "passage_decisions.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        records = [json.loads(line) for line in stream]
    decisions = {(row["Source"], row["Text"]): row for row in records}
    historical = {}
    pilot = read_json(args.pilot / "results.json")
    for snapshot in pilot["snapshots"]:
        for match in snapshot["matches"]:
            key = (match["Source"], match["Text"])
            if (
                key not in historical
                or snapshot["timestamp"] > historical[key]["timestamp"]
            ):
                historical[key] = {
                    **snapshot,
                    "status": match["status"],
                    "parse_evidence": str(
                        (args.pilot / "requests" / snapshot["parse_evidence"]).resolve()
                    ),
                }
                historical[key].pop("matches")
    table = pq.read_table(baseline)
    v1 = write_new(enrich(table, decisions, historical), paths[0])
    LOG.info(
        "V1 saved: assigned=%d unresolved=%d",
        v1.num_rows - v1["wiki_page_id"].null_count,
        v1["wiki_page_id"].null_count,
    )
    v1_hash = sha256(paths[0])
    wanted = {
        d["revision_id"]: d["wiki_page_id"]
        for d in records
        if d["wiki_page_id"] is not None
    }
    client = WikiClient(args.output)
    revisions = {}
    revision_ids = sorted(wanted)
    for offset in range(0, len(revision_ids), 50):
        batch = revision_ids[offset : offset + 50]
        data, evidence = client.query(
            {
                "action": "query",
                "prop": "revisions",
                "revids": "|".join(map(str, batch)),
                "rvprop": "ids|timestamp|sha1",
            }
        )
        for page in data["query"]["pages"]:
            for revision in page.get("revisions", []):
                revid = revision["revid"]
                if revid not in wanted or page["pageid"] != wanted[revid]:
                    raise ValueError("API revision/page identity mismatch")
                revisions[revid] = {
                    **revision,
                    "pageid": page["pageid"],
                    "evidence": str((args.output / "requests" / evidence).resolve()),
                }
        save_json(args.output / "revision_metadata.json", revisions)
        LOG.info("Revision timestamp batch: %d/%d", len(revisions), len(wanted))
    if set(revisions) != set(wanted):
        raise ValueError("Revision metadata is incomplete; preserve V1")
    v2 = write_new(enrich(table, decisions, historical, revisions), paths[1])
    raw_columns = [name for name in table.column_names if name != "wiki_page_id"]
    assert v1.select(raw_columns).equals(table.select(raw_columns), check_metadata=True)
    assert v2.select(raw_columns).equals(table.select(raw_columns), check_metadata=True)
    assert v1["wiki_page_id"].equals(v2["wiki_page_id"])
    assert sha256(baseline) == original_hash and sha256(paths[0]) == v1_hash
    summary = {
        "rows": table.num_rows,
        "baseline_assigned_rows": table.num_rows - table["wiki_page_id"].null_count,
        "new_historical_rows": table["wiki_page_id"].null_count
        - v1["wiki_page_id"].null_count,
        "assigned_rows": v2.num_rows - v2["wiki_page_id"].null_count,
        "unresolved_rows": v2["wiki_page_id"].null_count,
        "v1_revision_rows": v1.num_rows - v1["wiki_revision_id"].null_count,
        "v2_revision_rows": v2.num_rows - v2["wiki_revision_id"].null_count,
        "unique_baseline_revision_ids": len(wanted),
        "new_revision_metadata_requests": len(
            list((args.output / "requests").glob("*.json.gz"))
        ),
        "v1_statuses": dict(Counter(v1["wiki_match_status"].to_pylist())),
        "v2_statuses": dict(Counter(v2["wiki_match_status"].to_pylist())),
        "outputs_sha256": {p.name: sha256(p) for p in paths},
        "baseline_sha256": original_hash,
        "original_columns_unchanged": True,
        "baseline_nonnull_ids_preserved": True,
        "historical_search_run": False,
        "entity_extraction_run": False,
        "text_matching_run": False,
        "revision_semantics": "A saved matching revision, not proven extraction revision. Baseline metadata copied from previously audited accepted evidence without rematching text.",
    }
    assert (
        summary["new_historical_rows"] == 2707
        and summary["v2_revision_rows"] == summary["assigned_rows"]
    )
    save_json(args.output / "summary.json", summary)
    LOG.info("Staged export complete: %s", json.dumps(summary))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()

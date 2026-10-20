"""Download candidate IDs only, reusing the verified snapshot acquisition SQL.

Population S2T 7: change only the final projection of the saved measurement.
This does not classify candidates, retrieve native records, or add model rows.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

from GG_Data.pipeline.poc import ROOT, digest, read_json

MEASUREMENT_TAIL = """
SELECT COUNT(*) AS incoming_candidate_count,
       COALESCE(SUM(item_bytes), 0) AS full_record_bytes,
       COUNTIF(ARRAY_LENGTH(targets) = 1) AS single_incoming_with_outgoing,
       COUNTIF(ARRAY_LENGTH(targets) >= 2) AS multiple_incoming
FROM candidates"""


def ids_query(sql: str) -> str:
    """Keep all saved filters/ranks unchanged; replace only the aggregate."""
    if not sql.endswith(MEASUREMENT_TAIL):
        raise ValueError("Unexpected verified measurement query")
    return sql[: -len(MEASUREMENT_TAIL)] + "\nSELECT id FROM candidates"


def validate_ids(rows: list[dict], expected: int) -> list[str]:
    ids = [r["id"] for r in rows]
    if (
        len(ids) != expected
        or len(set(ids)) != len(ids)
        or any(not re.fullmatch(r"Q[1-9]\d*", qid) for qid in ids)
    ):
        raise ValueError("Candidate IDs differ from the verified measurement")
    return sorted(ids)


def run(prior: Path, store: Path, output: Path) -> dict:
    if output.exists() or any(
        not p.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs")
        for p in (store, output)
    ):
        raise ValueError("Use a new approved pipeline output directory")
    check = read_json(prior / "verification.json")
    report = read_json(prior / "report.json")
    if (
        check["status"] != "VERIFIED_MEASUREMENT_ONLY_DOWNLOAD_PENDING_CONSULTATION"
        or digest(prior / "report.json") != check["report_sha256"]
    ):
        raise ValueError("Expected verified candidate measurement")
    for name, sha in report["inputs"].items():
        if digest(Path(name)) != sha:
            raise ValueError(f"Measurement input changed: {name}")
    key = report["request"]["sql_sha256"]
    sql = (store / f"{key}.sql").read_text(encoding="utf-8")
    # The existing CLI hashes query text before Windows newline conversion.
    if hashlib.sha256(sql.encode()).hexdigest() != key:
        raise ValueError("Saved measurement query changed")
    original = read_json(store / f"{key}.json.gz")
    if original["rows"] != [report["measurement"]]:
        raise ValueError("Saved measurement result changed")
    reference = next(
        Path(p) for p in report["inputs"] if Path(p).name == "reference_manifest.json"
    )
    ref = read_json(reference)
    if read_json(store / "table_snapshot.json") != ref["table_snapshot"]:
        raise ValueError("Candidate cache snapshot differs")
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from bigquery_direct_wikidata import BigQueryData
    finally:
        sys.path.pop(0)
    client = BigQueryData(ref["project"], store)
    output.mkdir(parents=True)
    result = dict(
        status="RETRIEVING_CANDIDATE_IDS_ONLY",
        events_complete=False,
        event_rows_written=0,
        final_graph_written=False,
        code_sha256=digest(Path(__file__)),
        inputs={
            str(prior / "report.json"): digest(prior / "report.json"),
            str(prior / "verification.json"): digest(prior / "verification.json"),
        },
    )
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    try:
        rows = client.query(ids_query(sql))
        ids = validate_ids(rows, int(report["measurement"]["incoming_candidate_count"]))
        with gzip.open(output / "candidate_ids.json.gz", "wt", encoding="utf-8") as f:
            json.dump(ids, f)
        result.update(
            status="SNAPSHOT_CANDIDATE_IDS_RETRIEVED_ONLY",
            candidate_count=len(ids),
            request=client.requests[-1],
        )
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        result.update(status="BLOCKED_CANDIDATE_IDS", error=str(exc))
    result["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prior", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    # The legacy dry-run receipt contains the entire large SQL; retain it in
    # its cache rather than flooding terminal output with that saved evidence.
    logging.getLogger("bigquery_direct_wikidata").setLevel(logging.WARNING)
    result = run(args.prior, args.store, args.output)
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"inputs", "request"}})
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

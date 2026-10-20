"""Apply the provisional 5% rule from population S2T section 6.1.

Reuse the saved page-link diagnostic only. Keep scores >=5%, exclude scores
<5% from Event retrieval. Preserve model identities, matching and raw evidence.
Accept separate saved EN/JA reports; this does not restart Event acquisition.
"""

import argparse
import csv
import json
import re
from pathlib import Path

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.snapshot_link_relevance_probe import BASE

THRESHOLD_PERCENT = 5


def threshold_rows(rows: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for row in rows:
        qid = row["qid"]
        wiki = row.get("wiki", "enwiki")
        key = (wiki, qid)
        numerator, denominator = row["scope_linking_pages"], row["all_linking_pages"]
        if (
            wiki not in ("enwiki", "jawiki")
            or not re.fullmatch(r"Q\d+", qid)
            or key in seen
        ):
            raise ValueError(
                "Expected unique language/QID pairs; synthetic IDs excluded"
            )
        seen.add(key)
        if row.get("score_status") in (
            "UNAVAILABLE_SNAPSHOT_PAGE",
            "UNAVAILABLE_NO_INCOMING_LINKS",
        ):
            # S2T 6.1: missing in one language does not block another language.
            # Preserve an explicit unknown decision; never convert it to zero.
            if any(
                row[k] is not None
                for k in ("scope_linking_pages", "all_linking_pages", "relevance")
            ):
                raise ValueError(f"Unavailable score contains numeric evidence: {key}")
            result.append({**row, "keep_for_event_retrieval": None})
            continue
        if row.get("score_status", "SCORED") != "SCORED":
            raise ValueError(f"Unexpected score status: {key}")
        if (
            type(numerator) is not int
            or type(denominator) is not int
            or not 0 <= numerator <= denominator
            or denominator <= 0
        ):
            raise ValueError(f"Unknown or invalid counts require consultation: {qid}")
        if row["relevance"] != numerator / denominator:
            raise ValueError(f"Saved ratio disagrees with counts: {qid}")
        # Integer comparison includes exactly 5%; never round before filtering.
        keep = 100 * numerator >= THRESHOLD_PERCENT * denominator
        result.append({**row, "keep_for_event_retrieval": keep})
    return result


def run(source: Path | None = None, output: Path | None = None) -> dict:
    source = (
        source or BASE / "poc_10k_misc_snapshot_link_relevance_20261020/report.json"
    )
    saved = read_json(source)
    for name, expected in saved["outputs"].items():
        if digest(source.parent / name) != expected:
            raise ValueError(f"Saved diagnostic output changed: {name}")
    rows = threshold_rows(saved["rows"])
    output = output or BASE / "poc_10k_scope_concentration_5pct_20261020"
    output.mkdir()  # Keep earlier diagnostic outputs unchanged.
    with (output / "selection.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "status": (
            "COMPLETE_PER_LANGUAGE_THRESHOLD"
            if saved.get("population") == "RESOLVED_MISC_QIDS_IN_FROZEN_10K"
            else "COMPLETE_BOUNDED_THRESHOLD_TEST"
        ),
        "threshold_percent": THRESHOLD_PERCENT,
        "rule": "exclude score < 0.05; keep score >= 0.05",
        "evaluated_qids": len(rows),
        "kept_qids": [r["qid"] for r in rows if r["keep_for_event_retrieval"] is True],
        "excluded_qids": [
            r["qid"] for r in rows if r["keep_for_event_retrieval"] is False
        ],
        "unavailable_qids": [
            r["qid"] for r in rows if r["keep_for_event_retrieval"] is None
        ],
        "decision_scope": "per language; no cross-language QID decision",
        "dump_date": saved["dump_date"],
        "wiki": saved["wiki"],
        "missing_source_titles": saved["missing_source_titles"],
        "distinct_resolved_source_pages": saved["distinct_resolved_source_pages"],
        "rows": rows,
        "limits": saved["limits"][:2],
        "matches_changed": False,
        "model_rows_deleted": False,
        "event_retrieval_started": False,
        "network_requests": 0,
        "inputs": {str(p): digest(p) for p in (source, Path(__file__))},
        "outputs": {"selection.csv": digest(output / "selection.csv")},
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {k: v for k, v in report.items() if k != "rows"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.source, args.output)
    print(
        json.dumps(
            {k: v for k, v in report.items() if not k.endswith("_qids")}, indent=2
        )
    )

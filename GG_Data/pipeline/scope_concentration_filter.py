"""Apply the provisional 5% rule from population S2T section 6.1.

Reuse the saved page-link diagnostic only. Keep scores >=5%, exclude scores
<5% from Event retrieval. Preserve model identities, matching and raw evidence.
Accept separate saved EN/JA reports; this does not restart Event acquisition.
"""

import argparse
import csv
import json
import re
from fractions import Fraction
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


def combine_language_rows(english: list[dict], japanese: list[dict]) -> list[dict]:
    """S2T 6.1: use the highest available percentage, never pooled counts.

    Exact fractions select the maximum before the inclusive 5% comparison.
    Unknown in both languages remains unknown; it is not an exclusion.
    """
    languages = {}
    for wiki, source in (("enwiki", english), ("jawiki", japanese)):
        checked = threshold_rows(source)
        if not checked or any(row.get("wiki") != wiki for row in checked):
            raise ValueError(f"Expected a nonempty {wiki} report")
        languages[wiki] = {row["qid"]: row for row in checked}
    if languages["enwiki"].keys() != languages["jawiki"].keys():
        raise ValueError("Language reports contain different QID populations")
    result = []
    for qid, english_row in languages["enwiki"].items():
        evidence = [english_row, languages["jawiki"][qid]]
        scored = [r for r in evidence if r["keep_for_event_retrieval"] is not None]
        best = max(
            scored,
            key=lambda r: Fraction(r["scope_linking_pages"], r["all_linking_pages"]),
            default=None,
        )
        result.append(
            dict(
                qid=qid,
                name=english_row["name"],
                enwiki_relevance=evidence[0]["relevance"],
                jawiki_relevance=evidence[1]["relevance"],
                enwiki_score_status=evidence[0].get("score_status", "SCORED"),
                jawiki_score_status=evidence[1].get("score_status", "SCORED"),
                maximum_relevance=best["relevance"] if best else None,
                maximum_score_wiki=best["wiki"] if best else None,
                scope_linking_pages=best["scope_linking_pages"] if best else None,
                all_linking_pages=best["all_linking_pages"] if best else None,
                keep_for_event_retrieval=(
                    best["keep_for_event_retrieval"] if best else None
                ),
            )
        )
    return result


def run_combined(english: Path, japanese: Path, output: Path) -> dict:
    """Reuse complete acquisition reports without modifying either language."""
    reports = []
    for source in (english, japanese):
        saved = read_json(source)
        for name, expected in saved["outputs"].items():
            if digest(source.parent / name) != expected:
                raise ValueError(f"Saved diagnostic output changed: {name}")
        reports.append(saved)
    if reports[0]["dump_date"] != reports[1]["dump_date"] or any(
        r["population"] != "RESOLVED_MISC_QIDS_IN_FROZEN_10K" for r in reports
    ):
        raise ValueError("Expected the same frozen 10K population and snapshot")
    # Shared Entity/page manifest inputs must identify the same accepted data.
    shared = reports[0]["inputs"].keys() & reports[1]["inputs"].keys()
    manifests = [p for p in shared if p.endswith("manifest.json")]
    if not manifests or any(
        reports[0]["inputs"][p] != reports[1]["inputs"][p]
        or digest(Path(p)) != reports[0]["inputs"][p]
        for p in manifests
    ):
        raise ValueError("Language reports do not share unchanged input manifests")
    rows = combine_language_rows(reports[0]["rows"], reports[1]["rows"])
    output.mkdir()  # Preserve earlier diagnostic and threshold evidence.
    with (output / "selection.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = dict(
        status="COMPLETE_MAXIMUM_LANGUAGE_THRESHOLD",
        threshold_percent=THRESHOLD_PERCENT,
        rule="highest available language percentage; keep >=5%; both missing unknown",
        evaluated_qids=len(rows),
        kept_qids=[r["qid"] for r in rows if r["keep_for_event_retrieval"] is True],
        excluded_qids=[
            r["qid"] for r in rows if r["keep_for_event_retrieval"] is False
        ],
        unavailable_qids=[
            r["qid"] for r in rows if r["keep_for_event_retrieval"] is None
        ],
        dump_date=reports[0]["dump_date"],
        missing_source_titles={r["wiki"]: r["missing_source_titles"] for r in reports},
        rows=rows,
        matches_changed=False,
        model_rows_deleted=False,
        event_retrieval_started=False,
        network_requests=0,
        inputs={str(p): digest(p) for p in (english, japanese, Path(__file__))},
        outputs={"selection.csv": digest(output / "selection.csv")},
    )
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


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
    parser.add_argument("--japanese-source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.japanese_source:
        if not args.source or not args.output:
            parser.error("Combined mode requires --source and --output")
        report = run_combined(args.source, args.japanese_source, args.output)
    else:
        report = run(args.source, args.output)
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if not k.endswith("_qids") and k != "rows"
            },
            indent=2,
        )
    )

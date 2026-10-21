"""Diagnostic only: summarize linked Daniel entity scores for each Event.

User clarification, 21 October 2026: measure the related entities, not the
Event. Reuse population S2T 6.1's maximum available EN/JA score per entity.
Each distinct Daniel QID has equal weight, regardless of assertion count.
No choice of mean/min/max filter is approved or applied here. Missing entity
scores remain explicit; do not compute a complete statistic from a subset.
"""

import argparse
import csv
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.scope_concentration_filter import combine_language_rows


def summarize_events(events: list[dict], scores: list[dict]) -> list[dict]:
    by_qid = {r["qid"]: r for r in scores}
    if len(by_qid) != len(scores):
        raise ValueError("Duplicate entity score")
    result = []
    seen = set()
    for event in events:
        qid = event["qid"]
        related = sorted(set(event["daniel_qids"]))
        if qid in seen or event["eligible"] is not True or len(related) < 2:
            raise ValueError("Expected unique Events passing the two-entity gate")
        seen.add(qid)
        if not set(related) <= by_qid.keys():
            raise ValueError("A related Daniel entity has no score record")
        unknown = [q for q in related if by_qid[q]["maximum_relevance"] is None]
        # S2T 6.1: fractions retain original counts; never pool page counts
        # between entities, weight by mentions, or replace unknown with zero.
        values = [
            Fraction(by_qid[q]["scope_linking_pages"], by_qid[q]["all_linking_pages"])
            for q in related
            if q not in unknown
        ]
        complete = not unknown
        result.append(
            dict(
                qid=qid,
                linked_entity_qids=related,
                linked_entity_count=len(related),
                scored_entity_count=len(values),
                unknown_entity_qids=unknown,
                mean_relevance=float(sum(values) / len(values)) if complete else None,
                min_relevance=float(min(values)) if complete else None,
                max_relevance=float(max(values)) if complete else None,
            )
        )
    return result


def verified_report(path: Path) -> dict:
    report = read_json(path)
    verification = path.parent / "verification.json"
    if (
        verification.exists()
        and digest(path) != read_json(verification)["report_sha256"]
    ):
        raise ValueError(f"Changed report: {path}")
    for name, expected in report["outputs"].items():
        if digest(path.parent / name) != expected:
            raise ValueError(f"Changed saved evidence: {path.parent / name}")
    return report


def run(base: Path, output: Path) -> dict:
    if (output / "report.json").exists():
        raise ValueError("Preserve completed diagnostic outputs")
    paths = [base / "two_entity_gate/report.json", base / "content_review/report.json"]
    paths += [output / wiki / "report.json" for wiki in ("enwiki", "jawiki")]
    reports = [verified_report(p) for p in paths]
    en, ja = reports[2:]
    expected = "DISTINCT_LINKED_DANIEL_ENTITIES_FOR_EVENT_RELEVANCE_DIAGNOSTIC"
    if en["dump_date"] != ja["dump_date"] or any(
        r["population"] != expected for r in (en, ja)
    ):
        raise ValueError("Expected the same linked-entity population and snapshot")
    shared = en["inputs"].keys() & ja["inputs"].keys()
    manifests = [p for p in shared if p.endswith("manifest.json")]
    if not manifests or any(
        en["inputs"][p] != ja["inputs"][p] or digest(Path(p)) != en["inputs"][p]
        for p in manifests
    ):
        raise ValueError("Shared population or source-page manifest changed")
    entities = combine_language_rows(en["rows"], ja["rows"])
    events = read_json(base / "two_entity_gate/decisions.json")
    if {q for r in events for q in r["daniel_qids"]} != {r["qid"] for r in entities}:
        raise ValueError("Entity score coverage differs from linked population")
    rows = summarize_events(events, entities)
    with (base / "content_review/events_content.csv").open(encoding="utf-8-sig") as f:
        content = {r["qid"]: r for r in csv.DictReader(f)}
    for row in rows:
        row.update(
            name=content[row["qid"]]["label"],
            review_group=content[row["qid"]]["review_group"],
        )
    for name, values in (("entities.json", entities), ("events.json", rows)):
        (output / name).write_text(
            json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    with (output / "events.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = dict(
        status="COMPLETE_LINKED_ENTITY_RELEVANCE_DIAGNOSTIC_ONLY",
        event_count=len(rows),
        distinct_linked_entities=len(entities),
        unknown_entity_count=sum(r["maximum_relevance"] is None for r in entities),
        unknown_event_count=sum(r["mean_relevance"] is None for r in rows),
        group_counts=dict(Counter(r["review_group"] for r in rows)),
        diagnostic_at_least_5pct_counts={
            metric: sum(r[metric] is not None and r[metric] >= 0.05 for r in rows)
            for metric in ("mean_relevance", "min_relevance", "max_relevance")
        },
        rule="maximum EN/JA per distinct linked Daniel QID, then unweighted mean/min/max per Event; missing remains unknown",
        filter_selected=False,
        filter_applied=False,
        event_rows_written=0,
        inputs={str(p): digest(p) for p in paths + [Path(__file__)]},
        outputs={
            n: digest(output / n)
            for n in ("entities.json", "events.json", "events.csv")
        },
    )
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.base, args.output), indent=2))

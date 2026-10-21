"""10K Event selection, population S2T 6.1/7; no graph or identity changes.

The 2% Event cutoff is separate from the existing 5% MISC retrieval filter.
The user approved holding its 619 unknown MISC QIDs aside for this full POC.
Native acquisition and the two-entity gate must precede Event selection.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from GG_Data.pipeline.event_linked_entity_relevance_probe import (
    summarize_events,
    verified_report,
)
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.scope_concentration_filter import combine_language_rows
from GG_Data.pipeline.snapshot_link_relevance_probe import run as measure

EVENT_THRESHOLD_PERCENT = 2
BASE = ROOT / "GG_Data/pipeline/outputs"


def select_events(events: list[dict], scores: list[dict]) -> list[dict]:
    """S2T 6.1: exact maximum, inclusive 2%; missing requires consultation.

    summarize_events validates distinct endpoints and the upstream two-entity
    gate. Unknowns never become zero or a decision based on a measured subset.
    Other entity scores below 5% are still valid Event evidence; only the MISC
    retrieval stage uses the separate 5% cutoff.
    """
    by_qid = {row["qid"]: row for row in scores}
    rows = summarize_events(events, scores)
    for row in rows:
        known = not row["unknown_entity_qids"]
        maximum = (
            max(
                Fraction(
                    by_qid[q]["scope_linking_pages"],
                    by_qid[q]["all_linking_pages"],
                )
                for q in row["linked_entity_qids"]
            )
            if known
            else None
        )
        keep = maximum >= Fraction(EVENT_THRESHOLD_PERCENT, 100) if known else None
        row.update(
            keep_event=keep,
            event_threshold_percent=EVENT_THRESHOLD_PERCENT,
            decision_reason=(
                "UNKNOWN_LINKED_ENTITY_SCORE_REQUIRES_CONSULTATION"
                if keep is None
                else (
                    "EVENT_MAXIMUM_AT_LEAST_2PCT"
                    if keep
                    else "EVENT_MAXIMUM_BELOW_2PCT"
                )
            ),
        )
    return rows


def prepare(output: Path) -> dict:
    """Pin the frozen 10K sources and preserve every model row (S2T 1/6.1).

    Selection lists are retrieval scope only, never rewritten Entities or
    Mentions. Unknown MISC QIDs are held aside under the explicit user approval.
    """
    entities = BASE / "poc_10k_entities_snapshot_first_20261020"
    entity_manifest = read_json(entities / "manifest.json")
    if (
        digest(entities / "manifest.json")
        != read_json(entities / "verification.json")["manifest_sha256"]
    ):
        raise ValueError("Frozen Entity manifest changed")
    for name, expected in entity_manifest["outputs"].items():
        if digest(entities / name) != expected:
            raise ValueError(f"Frozen Entity output changed: {name}")
    source = (
        BASE / "poc_10k_scope_concentration_maximum_language_5pct_20261020/report.json"
    )
    saved = verified_report(source)
    if saved["threshold_percent"] != 5:
        raise ValueError("The separate MISC retrieval filter must remain 5%")
    records = read_json(entities / "full_records.json.gz")
    decisions = {row["qid"]: row["keep_for_event_retrieval"] for row in saved["rows"]}
    if not decisions.keys() <= records.keys():
        raise ValueError("MISC scope contains IDs outside the frozen Daniel population")
    excluded = sorted(q for q in records if decisions.get(q, True) is False)
    held = sorted(q for q in records if decisions.get(q, True) is None)
    retained = sorted(set(records) - set(excluded) - set(held))
    model = read_json(entities / "entities.json.gz")
    names = {row["entity_id"]: row["name"] for row in model}
    output.mkdir(parents=True, exist_ok=False)
    selection = [{"qid": q, "title": names[q]} for q in retained]
    (output / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    scope = dict(
        original_qids=len(records),
        retained_qids=retained,
        below_misc_5pct_qids=excluded,
        held_unknown_misc_qids=held,
        unknown_policy="User-approved hold aside for the full 10K POC; model records preserved",
        entity_threshold_percent=5,
        event_threshold_percent=EVENT_THRESHOLD_PERCENT,
    )
    (output / "retrieval_scope.json").write_text(
        json.dumps(scope, indent=2), encoding="utf-8"
    )
    manifest = dict(
        population="RETAINED_DANIEL_QIDS_FOR_10K_EVENT_SELECTION",
        inputs={str(p): digest(p) for p in (entities / "manifest.json", source)},
        outputs={
            n: digest(output / n) for n in ("selection.json", "retrieval_scope.json")
        },
        event_rows_written=0,
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return scope


def measure_population(output: Path) -> dict:
    """Reuse the existing saved dump/count/redirect implementation verbatim."""
    started = perf_counter()
    scope = prepare(output)
    report = dict(
        status="MEASURING_RETAINED_ENTITY_RELEVANCE",
        scope_counts={
            k: len(v) if isinstance(v, list) else v for k, v in scope.items()
        },
        event_rows_written=0,
        final_graph_written=False,
        code_sha256=digest(Path(__file__)),
    )

    def save() -> None:
        report["elapsed_seconds"] = perf_counter() - started
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    save()
    try:
        languages = [
            measure(wiki, True, output / wiki, output / "selection.json")
            for wiki in ("enwiki", "jawiki")
        ]
        scores = combine_language_rows(languages[0]["rows"], languages[1]["rows"])
        if {r["qid"] for r in scores} != set(scope["retained_qids"]):
            raise ValueError("Measured scope differs from the retained population")
        (output / "entity_scores.json").write_text(
            json.dumps(scores, indent=2), encoding="utf-8"
        )
        report.update(
            status="ENTITY_MEASUREMENT_COMPLETE_EVENT_DISCOVERY_PENDING",
            scored_qids=sum(r["maximum_relevance"] is not None for r in scores),
            unavailable_qids=[
                r["qid"] for r in scores if r["maximum_relevance"] is None
            ],
            event_threshold_percent=EVENT_THRESHOLD_PERCENT,
            score_status_counts=dict(
                Counter(r["maximum_score_wiki"] or "unknown" for r in scores)
            ),
            outputs={
                n: digest(output / n) for n in ("manifest.json", "entity_scores.json")
            },
        )
    except Exception as exc:
        report.update(
            status="STOPPED_FOR_CONSULTATION", error=f"{type(exc).__name__}: {exc}"
        )
        raise
    finally:
        save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(measure_population(args.output), indent=2))

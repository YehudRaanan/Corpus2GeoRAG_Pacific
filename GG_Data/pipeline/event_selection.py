"""10K Event selection, population S2T 6.1/7; no graph or identity changes.

Events require two distinct retained Daniel QIDs and >=2% maximum linked-entity
relevance. Missing scores contribute zero to selection, with evidence preserved.
The user approved holding its 619 unknown MISC QIDs aside for this full POC.
Native recognition and mapped/excluded assertion checks precede selection.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from GG_Data.pipeline.event_linked_entity_relevance_probe import verified_report
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.scope_concentration_filter import combine_language_rows
from GG_Data.pipeline.snapshot_link_relevance_probe import run as measure

MINIMUM_DANIEL_QIDS = 2
EVENT_THRESHOLD_PERCENT = 2
EVENT_AGGREGATION = "maximum_missing_zero"
EVENT_MISSING_POLICY = "zero_for_selection_preserve_missing_metadata"
BASE = ROOT / "GG_Data/pipeline/outputs"
SCORES = BASE / "poc_10k_event_selection_2pct_redirect_priority_20261021"
SCORES_SHA = "3e46b4da5b18621aa4513a788adb75e4bc6b9c0c581c7591b0d9c3fd09f96212"


def load_scores(
    retained_qids: set[str], scores_dir: Path | None = None
) -> dict[str, Fraction | None]:
    """Reuse the approved language maxima; missing records are not unscored."""
    directory = scores_dir or SCORES
    path = directory / "entity_scores.json"
    report = read_json(directory / "report.json")
    expected = report["outputs"][path.name]
    if digest(path) != expected or (directory == SCORES and expected != SCORES_SHA):
        raise ValueError("Approved retained-entity scores changed")
    rows = read_json(path)
    if len(rows) != len(retained_qids) or {r["qid"] for r in rows} != retained_qids:
        raise ValueError("Entity scores do not exactly cover retained Daniel QIDs")
    result = {}
    for row in rows:
        value = row["maximum_relevance"]
        numerator, denominator = row["scope_linking_pages"], row["all_linking_pages"]
        languages = [row["enwiki_relevance"], row["jawiki_relevance"]]
        if value is None:
            if any(v is not None for v in [numerator, denominator, *languages]):
                raise ValueError("Unscored entity has numeric score evidence")
            result[row["qid"]] = None
        else:
            if (
                type(numerator) is not int
                or type(denominator) is not int
                or not 0 <= numerator <= denominator
                or denominator <= 0
                or value != numerator / denominator
                or value != max(v for v in languages if v is not None)
            ):
                raise ValueError("Entity score disagrees with saved page counts")
            result[row["qid"]] = Fraction(numerator, denominator)
    return result


def select_events(
    events: list[dict],
    retained_qids: set[str],
    scores: dict[str, Fraction | None],
) -> list[dict]:
    """S2T 7: >=2 endpoints and maximum endpoint score >=2%; missing is zero.

    Repeated mentions, predicates and reverse views cannot add endpoints.
    This is the deliberately inclusive 21 October rule; related entities can
    give an unrelated item a high score. See the S2T limitation before tuning.
    Explicit None contributes zero but remains visible in missing metadata.
    Missing score rows are integrity errors. The known-score mean is retained
    only as a diagnostic; it does not control inclusion.
    The separate 5% MISC scope filter precedes this decision.
    """
    rows, seen = [], set()
    for event in events:
        qid = event["qid"]
        related = sorted(set(event["daniel_qids"]))
        recognized = event["event_hierarchy_match"]
        if qid in seen or type(recognized) is not bool:
            raise ValueError("Expected unique Events with explicit recognition")
        if not set(related) <= retained_qids:
            raise ValueError("Event endpoint is outside retained Daniel scope")
        if not set(related) <= scores.keys() or any(
            scores[q] is not None and not isinstance(scores[q], Fraction)
            for q in related
        ):
            raise ValueError("Expected explicit exact scores or unscored records")
        seen.add(qid)
        unscored = [q for q in related if scores[q] is None]
        known = [scores[q] for q in related if scores[q] is not None]
        maximum = max(known, default=None)
        effective = max(
            (scores[q] or Fraction(0) for q in related), default=Fraction(0)
        )
        average = sum(known, Fraction(0)) / len(known) if known else None
        meets_relevance = 100 * effective >= EVENT_THRESHOLD_PERCENT
        enough = len(related) >= MINIMUM_DANIEL_QIDS
        keep = recognized and enough and meets_relevance
        rows.append(
            dict(
                qid=qid,
                linked_entity_qids=related,
                linked_entity_count=len(related),
                keep_event=keep,
                minimum_distinct_daniel_qids=MINIMUM_DANIEL_QIDS,
                event_threshold_percent=EVENT_THRESHOLD_PERCENT,
                maximum_known_relevance=float(maximum) if maximum is not None else None,
                effective_event_relevance=float(effective),
                average_known_relevance=float(average) if average is not None else None,
                scored_entity_count=len(known),
                relevance_aggregation=EVENT_AGGREGATION,
                missing_score_policy=EVENT_MISSING_POLICY,
                unscored_entity_qids=unscored,
                known_relevance_pass=meets_relevance,
                decision_reason=(
                    "NOT_RECOGNIZED"
                    if not recognized
                    else (
                        "FEWER_THAN_TWO_DISTINCT_DANIEL_QIDS"
                        if not enough
                        else (
                            "MAXIMUM_AT_LEAST_2PCT"
                            if meets_relevance
                            else "MAXIMUM_BELOW_2PCT"
                        )
                    )
                ),
            )
        )
    return rows


def prepare(
    output: Path,
    entities: Path | None = None,
    scope_report: Path | None = None,
) -> dict:
    """Pin the frozen 10K sources and preserve every model row (S2T 1/6.1).

    Selection lists are retrieval scope only, never rewritten Entities or
    Mentions. Unknown MISC QIDs are held aside under the explicit user approval.
    """
    entities = entities or BASE / "poc_10k_entities_snapshot_first_20261020"
    entity_manifest = read_json(entities / "manifest.json")
    if (
        digest(entities / "manifest.json")
        != read_json(entities / "verification.json")["manifest_sha256"]
    ):
        raise ValueError("Frozen Entity manifest changed")
    for name, expected in entity_manifest["outputs"].items():
        if digest(entities / name) != expected:
            raise ValueError(f"Frozen Entity output changed: {name}")
    source = scope_report or (
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
        event_relevance_aggregation=EVENT_AGGREGATION,
        event_missing_score_policy=EVENT_MISSING_POLICY,
        minimum_distinct_daniel_qids=MINIMUM_DANIEL_QIDS,
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

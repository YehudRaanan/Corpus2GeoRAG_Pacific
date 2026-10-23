"""Controlled 30-case regression gate; population S2T section 3.1.

Cases come from the existing review, before scoring. Reconstruct page pools
from saved EN/JA links. Freeze the baseline global reference pools for this
diagnostic only; a production rebuild must recompute its page-matched pool.
No manual assignment, new entity, network lookup or full matching run occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from bilingual_page_pilot import ancestry, choose, digest, read, synthetic_id
from direct_wikidata_pilot import SEED, page_candidate_ids, page_find
from full_direct_wikidata import page_indexes, save
from generate_candidates import NameIndex
from matching_scoring import POLICY, require_measurements

GOOD = (2, 5, 7, 8, 9, 10, 16, 17, 19, 20, 23, 25, 28, 46, 50, 73, 88)
WRONG = (11, 18, 27, 43, 44, 48, 51, 55, 59, 62, 90, 92, 94)
STAGES = ("PAGE_DIRECT_WIKIDATA", "ALREADY_MATCHED", "FRESH_WWII")


def replay(case: dict, metadata: dict, penalized: bool) -> dict:
    attempts = []
    for stage in STAGES:
        decision = choose(
            case["candidates"][stage],
            case["original_type"],
            metadata,
            random.Random(f"{SEED}:{stage}:{case['mention_id']}"),
            prefer_single_wikidata_type=True,
            apply_penalties=penalized,
        )
        attempts.append(dict(stage=stage, **decision))
        if decision["status"] == "MATCHED":
            return dict(
                assigned_id=decision["entity_id"], stage=stage, attempts=attempts
            )
    reason = next(
        (
            s
            for s in (
                "TYPE_MISMATCH",
                "TYPE_UNKNOWN",
                "NO_ADJUSTED_SCORE_ABOVE_THRESHOLD",
            )
            if any(a["status"] == s for a in attempts)
        ),
        "NO_NAME_ABOVE_THRESHOLD",
    )
    return dict(
        assigned_id=synthetic_id(case, reason), stage="SYNTHETIC", attempts=attempts
    )


def prepare(source: Path, review: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Preserve earlier evaluation outputs")
    audit = read(review)
    metadata = read(source / "entity_metadata.json.gz")
    evidence = read(source / "candidate_evidence.json.gz")
    world = read(source / "world.json.gz")
    manifest = read(source / "manifest.json")
    for name in (
        "entity_metadata.json.gz",
        "candidate_evidence.json.gz",
        "world.json.gz",
    ):
        if digest(source / name) != manifest["outputs"][name]:
            raise ValueError(f"Matching source changed: {name}")
    cases = []
    for row in audit["rows"]:
        if row["index"] not in GOOD + WRONG:
            continue
        source_title = row["source_page"]
        page = (
            source
            / "pages"
            / (hashlib.sha256(source_title.encode()).hexdigest() + ".json.gz")
        )
        if digest(page) != manifest["page_evidence"][page.name]:
            raise ValueError("Page source changed")
        pool = page_candidate_ids(read(page)["articles"])
        if pool != set(evidence["page_pools"][source_title]):
            raise ValueError("Page pool differs from saved source links")
        original, cleaned, maps = page_indexes(pool, metadata)
        candidates = page_find(original, cleaned, row["daniel_name"], maps)
        cases.append(
            dict(
                index=row["index"],
                mention_id=row["mention_id"],
                name=row["daniel_name"],
                source_page=source_title,
                original_type=row["identity_matching_trace"]["type_metadata"][
                    "original_type"
                ],
                baseline_qid=row["place_id"],
                expected_baseline="CORRECT" if row["index"] in GOOD else "WRONG",
                reviewed_reason=row["reason"],
                context=row["mention_context_excerpt"],
                candidates={STAGES[0]: candidates},
            )
        )
    for stage, pool, names in (
        (STAGES[1], evidence["frozen_matched_ids"], metadata),
        (STAGES[2], sorted(world), world),
    ):
        index = NameIndex(pool, names)
        for case in cases:
            case["candidates"][stage] = index.find(case["name"], "MISC", 0.8)
        del index
    needed = {
        c["entity_id"]
        for case in cases
        for candidates in case["candidates"].values()
        for c in candidates
    }
    closure = ancestry(
        [t for q in needed for t in metadata[q].get("direct_types", [])], metadata
    )
    subset = {q: metadata[q] for q in needed | closure if q in metadata}
    for case in cases:
        baseline = replay(case, subset, False)
        if baseline["assigned_id"] != case["baseline_qid"]:
            raise ValueError(
                f"Baseline replay differs at reviewed case {case['index']}"
            )
    output.mkdir(parents=True)
    save(output / "cases.json", cases)
    save(output / "metadata.json.gz", subset)
    save(
        output / "selection.json",
        [dict(qid=q, title=metadata[q].get("label", q)) for q in sorted(needed)],
    )
    report = dict(
        status="FROZEN_30_CASE_BASELINE_REPRODUCED",
        cases=len(cases),
        correct_baseline=len(GOOD),
        wrong_baseline=len(WRONG),
        candidate_qids=len(needed),
        production_pools_reused=False,
        diagnostic_pools="FIXED_VERIFIED_BASELINE_REFERENCES",
        inputs={str(p): digest(p) for p in (review, source / "manifest.json")},
        population="REVIEWED_30_MATCHING_CANDIDATES",
        outputs={p.name: digest(p) for p in output.iterdir()},
    )
    save(output / "manifest.json", report)
    return report


def evaluate(output: Path, relevance_file: Path) -> dict:
    if (output / "report.json").exists():
        raise ValueError("Preserve earlier evaluation")
    manifest = read(output / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(output / name) != sha:
            raise ValueError("Frozen test input changed")
    cases = read(output / "cases.json")
    metadata = read(output / "metadata.json.gz")
    measured = read(relevance_file)
    receipt = read(relevance_file.parent / "report.json")
    if receipt.get("status") != "MATCHING_CANDIDATE_RELEVANCE_COMPLETE" or receipt[
        "outputs"
    ].get(relevance_file.name) != digest(relevance_file):
        raise ValueError("Candidate relevance receipt differs or is incomplete")
    needed = {r["qid"] for r in read(output / "selection.json")}
    require_measurements(measured, needed)
    for qid in needed:
        metadata[qid] = {**metadata[qid], "matching_relevance": measured[qid]}
    rows = []
    for case in cases:
        updated = replay(case, metadata, True)
        assigned = updated["assigned_id"]
        outcome = (
            case["expected_baseline"]
            if assigned == case["baseline_qid"]
            else (
                "UNRESOLVED"
                if assigned.startswith("SYN_")
                else "CHANGED_QID_REQUIRES_REVIEW"
            )
        )
        rows.append(
            {
                **case,
                "updated": updated,
                "outcome": outcome,
                "regression": case["expected_baseline"] == "CORRECT"
                and outcome != "CORRECT",
            }
        )
    counts = dict(Counter(r["outcome"] for r in rows))
    regressions = [r["index"] for r in rows if r["regression"]]
    passed = (
        not regressions
        and not counts.get("CHANGED_QID_REQUIRES_REVIEW", 0)
        and counts.get("WRONG", 0) <= len(WRONG)
    )
    report = dict(
        status="GATE_PASSED" if passed else "STOPPED_FOR_CONSULTATION",
        scoring_policy=POLICY,
        sample_size=len(rows),
        baseline={"correct": len(GOOD), "wrong": len(WRONG), "unresolved": 0},
        updated_counts=counts,
        regression_case_indices=regressions,
        full_matching_authorized_by_gate=passed,
        production_outputs_changed=False,
        code_sha256={
            p.name: digest(p)
            for p in (
                Path(__file__),
                Path(__file__).with_name("matching_scoring.py"),
                Path(__file__).with_name("bilingual_page_pilot.py"),
                Path(__file__).with_name("full_direct_wikidata.py"),
            )
        },
        limitation="Controlled fixed-reference regression test; not a population accuracy estimate.",
        inputs={str(p): digest(p) for p in (output / "manifest.json", relevance_file)},
        rows=rows,
    )
    save(output / "report.json", report)
    return {k: v for k, v in report.items() if k != "rows"}


def accept_review(output: Path, review_file: Path) -> dict:
    """Close the diagnostic gate after source review and owner consultation.

    This records the owner's 23 October instruction to continue with the
    approved formula and four known failures. It changes no QID or gold case.
    Preserve the original automatic report and the separate source review.
    """
    target = output / "reviewed_report.json"
    if target.exists():
        raise ValueError("Preserve earlier reviewed gate")
    report_file = output / "report.json"
    report, review = read(report_file), read(review_file)
    if review["automatic_report_sha256"] != digest(report_file):
        raise ValueError("Review belongs to a different automatic result")
    source = Path(review["source_records"])
    if digest(source) != review["source_records_sha256"]:
        raise ValueError("Reviewed source records changed")
    changed = {
        r["index"]: r
        for r in report["rows"]
        if r["outcome"] == "CHANGED_QID_REQUIRES_REVIEW"
    }
    reviewed = {r["index"]: r for r in review["cases"]}
    if set(reviewed) != set(changed) or len(reviewed) != len(review["cases"]):
        raise ValueError("Changed QID review is incomplete or duplicated")
    rows = []
    for row in report["rows"]:
        decision = reviewed.get(row["index"])
        if decision:
            if decision["assigned_id"] != row["updated"]["assigned_id"] or decision[
                "outcome"
            ] not in {"CORRECT", "WRONG"}:
                raise ValueError("Review changes an assignment or has no outcome")
            row = {**row, "outcome": decision["outcome"], "source_review": decision}
        rows.append(row)
    counts = dict(Counter(r["outcome"] for r in rows))
    regressions = [
        r["index"]
        for r in rows
        if r["expected_baseline"] == "CORRECT" and r["outcome"] != "CORRECT"
    ]
    if (
        regressions
        or counts != review["reviewed_counts"]
        or counts.get("WRONG", 0) > report["baseline"]["wrong"]
    ):
        raise ValueError("Source-reviewed gate has degradation or differing counts")
    result = {
        **report,
        "rows": rows,
        "updated_counts": counts,
        "status": "GATE_PASSED_AFTER_SOURCE_REVIEW_AND_OWNER_APPROVAL",
        "full_matching_authorized_by_gate": True,
        "regression_case_indices": regressions,
        "owner_decision": "Continue with the approved formula",
        "known_wrong_case_indices": [
            r["index"] for r in rows if r["outcome"] == "WRONG"
        ],
        "review_inputs": {
            str(p): digest(p) for p in (report_file, review_file, source)
        },
    }
    save(target, result)
    return {k: v for k, v in result.items() if k != "rows"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "evaluate", "accept-review"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--relevance", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (
        prepare(args.source, args.review, args.output)
        if args.phase == "prepare"
        else (
            accept_review(args.output, args.review)
            if args.phase == "accept-review"
            else evaluate(args.output, args.relevance)
        )
    )
    print(json.dumps(result, indent=2))

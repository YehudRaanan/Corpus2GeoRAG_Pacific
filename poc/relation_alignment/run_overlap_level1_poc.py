"""Test whether QID-pair overlap can inherit Wikidata Level 1 parents."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from run_data_driven_mapping_poc import (
    GROUP_FIELDS,
    evidence_score,
    evidence_status,
)

HERE = Path(__file__).resolve().parent
SOURCE_MAP = HERE / "source_ontology_map" / "source_ontology_level1_level2.csv"
EVENTKG_OVERLAP = HERE / "mapping_discovery" / "eventkg_wikidata_candidates.csv"
WARSAMPO_OVERLAP = HERE / "audit_2026-10-11" / "type_mapping_ranking.csv"
OUT = HERE / "overlap_level1_poc"
REPORT = HERE / "OVERLAP_LEVEL1_POC_2026-10-11.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def wikidata_property(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def wikidata_parents(
    source_rows: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    parents: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        if row["source"] != "Wikidata" or row["resolution_status"] != "DECLARED_PARENT":
            continue
        parents[wikidata_property(row["normalized_level2_uri"])].append(
            {
                "level1_uri": row["level1_uri"],
                "level1_label": row["level1_label"],
                "parent_basis": row["mapping_basis"],
            }
        )
    return parents


def decide_eventkg_group(
    ranked: list[dict[str, str]], parent_map: dict[str, list[dict[str, str]]]
) -> tuple[str, float]:
    top = ranked[0]
    margin = (
        round(evidence_score(top) - evidence_score(ranked[1]), 1)
        if len(ranked) > 1
        else 100.0
    )
    if evidence_status(top) != "STRONG_CANDIDATE" or margin < 15:
        return "KEEP_UNRESOLVED", margin
    if not parent_map.get(top["wd_property"]):
        return "LEVEL2_ONLY_NO_WIKIDATA_PARENT", margin
    return "PROVISIONAL_LEVEL1", margin


def warsampo_evidence_status(row: dict[str, str]) -> str:
    if (
        int(row["shared_pairs"]) >= 20
        and float(row["pct_of_war_co_connected"]) >= 90
        and float(row["pct_of_wd_co_connected"]) >= 80
    ):
        return "STRONG_CANDIDATE"
    return "INSUFFICIENT_SUPPORT"


def build() -> dict[str, object]:
    source_rows = read_csv(SOURCE_MAP)
    unresolved = [
        row for row in source_rows if row["resolution_status"] == "NO_DECLARED_PARENT"
    ]
    unresolved_by_key = {
        (row["source"], row["source_predicate"]): row for row in unresolved
    }
    parent_map = wikidata_parents(source_rows)

    eventkg_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(EVENTKG_OVERLAP):
        if ("EventKG", row["ek_role"]) in unresolved_by_key:
            eventkg_groups[tuple(row[field] for field in GROUP_FIELDS)].append(row)

    eventkg_rankings: list[dict[str, object]] = []
    eventkg_decisions: list[dict[str, object]] = []
    level1_candidates: list[dict[str, object]] = []
    relation_actions: dict[tuple[str, str], set[str]] = defaultdict(set)

    for key, candidates in sorted(eventkg_groups.items()):
        ranked = sorted(
            candidates,
            key=lambda row: (
                -evidence_score(row),
                -int(row["shared_pairs"]),
                row["wd_property"],
                row["direction"],
            ),
        )
        action, margin = decide_eventkg_group(ranked, parent_map)
        source_row = unresolved_by_key[("EventKG", key[0])]
        relation_actions[("EventKG", source_row["level2_uri"])].add(action)
        top = ranked[0]
        eventkg_decisions.append(
            {
                "source": "EventKG",
                "source_relation_uri": source_row["level2_uri"],
                **dict(zip(GROUP_FIELDS, key, strict=True)),
                "top_wd_property": top["wd_property"],
                "top_direction": top["direction"],
                "top_score": evidence_score(top),
                "top_shared_pairs": top["shared_pairs"],
                "top_evidence_status": evidence_status(top),
                "runner_up": ranked[1]["wd_property"] if len(ranked) > 1 else "",
                "score_margin": margin,
                "wikidata_parent_count": len(parent_map.get(top["wd_property"], [])),
                "automatic_action": action,
            }
        )
        for rank, candidate in enumerate(ranked, start=1):
            candidate_parents = parent_map.get(candidate["wd_property"], [])
            eventkg_rankings.append(
                {
                    "source": "EventKG",
                    "source_relation_uri": source_row["level2_uri"],
                    **dict(zip(GROUP_FIELDS, key, strict=True)),
                    "rank": rank,
                    "wd_property": candidate["wd_property"],
                    "direction": candidate["direction"],
                    "shared_pairs": candidate["shared_pairs"],
                    "co_connected_pairs": candidate["ek_co_connected_pairs"],
                    "pair_coverage_pct": candidate["pct_of_ek_co_connected"],
                    "after_largest_target_pct": candidate["after_largest_target_pct"],
                    "held_out_pairs": candidate["test_pairs"],
                    "held_out_coverage_pct": candidate["test_pct_of_ek_co_connected"],
                    "evidence_score": evidence_score(candidate),
                    "evidence_status": evidence_status(candidate),
                    "wikidata_parent_count": len(candidate_parents),
                    "top_group_action": action if rank == 1 else "NOT_TOP_RANKED",
                    "example_qid_pairs": candidate["example_qid_pairs"],
                }
            )
            for parent in candidate_parents:
                level1_candidates.append(
                    {
                        "source": "EventKG",
                        "source_relation_uri": source_row["level2_uri"],
                        "source_relation": key[0],
                        "context": "|".join(key[1:]),
                        "wd_property": candidate["wd_property"],
                        "direction": candidate["direction"],
                        "candidate_rank": rank,
                        "shared_pairs": candidate["shared_pairs"],
                        "evidence_status": evidence_status(candidate),
                        **parent,
                        "inheritance_status": (
                            "PROVISIONAL_LEVEL1"
                            if rank == 1 and action == "PROVISIONAL_LEVEL1"
                            else "REVIEW_CANDIDATE"
                        ),
                    }
                )

    warsampo_rankings: list[dict[str, object]] = []
    war_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(WARSAMPO_OVERLAP):
        if ("WarSampo", row["war_predicate"].rsplit("/", 1)[-1]) in unresolved_by_key:
            source_row = unresolved_by_key[
                ("WarSampo", row["war_predicate"].rsplit("/", 1)[-1])
            ]
            if source_row["level2_uri"] == row["war_predicate"]:
                war_groups[row["war_predicate"]].append(row)

    for predicate, candidates in sorted(war_groups.items()):
        ranked = sorted(
            candidates,
            key=lambda row: (
                -min(
                    float(row["pct_of_war_co_connected"]),
                    float(row["pct_of_wd_co_connected"]),
                ),
                -int(row["shared_pairs"]),
                row["wd_property"],
            ),
        )
        top = ranked[0]
        top_status = warsampo_evidence_status(top)
        action = (
            "PROVISIONAL_LEVEL1"
            if top_status == "STRONG_CANDIDATE" and parent_map.get(top["wd_property"])
            else (
                "LEVEL2_ONLY_NO_WIKIDATA_PARENT"
                if top_status == "STRONG_CANDIDATE"
                else "KEEP_UNRESOLVED"
            )
        )
        relation_actions[("WarSampo", predicate)].add(action)
        for rank, candidate in enumerate(ranked, start=1):
            status = warsampo_evidence_status(candidate)
            candidate_parents = parent_map.get(candidate["wd_property"], [])
            warsampo_rankings.append(
                {
                    "source": "WarSampo",
                    "source_relation_uri": predicate,
                    "rank": rank,
                    "wd_property": candidate["wd_property"],
                    "direction": candidate["direction"],
                    "shared_pairs": candidate["shared_pairs"],
                    "war_co_connected_pairs": candidate["war_co_connected_pairs"],
                    "wd_co_connected_pairs": candidate["wd_co_connected_pairs"],
                    "war_coverage_pct": candidate["pct_of_war_co_connected"],
                    "wd_coverage_pct": candidate["pct_of_wd_co_connected"],
                    "evidence_status": status,
                    "wikidata_parent_count": len(candidate_parents),
                    "top_group_action": action if rank == 1 else "NOT_TOP_RANKED",
                }
            )
            for parent in candidate_parents:
                level1_candidates.append(
                    {
                        "source": "WarSampo",
                        "source_relation_uri": predicate,
                        "source_relation": predicate.rsplit("/", 1)[-1],
                        "context": "screened WarSampo-Wikidata QID pairs",
                        "wd_property": candidate["wd_property"],
                        "direction": candidate["direction"],
                        "candidate_rank": rank,
                        "shared_pairs": candidate["shared_pairs"],
                        "evidence_status": status,
                        **parent,
                        "inheritance_status": (
                            "PROVISIONAL_LEVEL1"
                            if rank == 1 and action == "PROVISIONAL_LEVEL1"
                            else "REVIEW_CANDIDATE"
                        ),
                    }
                )

    coverage = []
    for row in unresolved:
        key = (row["source"], row["level2_uri"])
        actions = relation_actions.get(key, set())
        if row["source"] == "Wikidata":
            status = "REFERENCE_SOURCE_NOT_EVALUATED"
        elif "PROVISIONAL_LEVEL1" in actions:
            status = "PROVISIONAL_LEVEL1"
        elif "LEVEL2_ONLY_NO_WIKIDATA_PARENT" in actions:
            status = "LEVEL2_ONLY_NO_WIKIDATA_PARENT"
        elif actions:
            has_candidate = any(
                candidate["source"] == row["source"]
                and candidate["source_relation_uri"] == row["level2_uri"]
                for candidate in level1_candidates
            )
            status = "LEVEL1_REVIEW_CANDIDATE" if has_candidate else "OVERLAP_WITHOUT_LEVEL1"
        else:
            status = "NO_AVAILABLE_QID_PAIR_OVERLAP"
        coverage.append(
            {
                "source": row["source"],
                "source_predicate": row["source_predicate"],
                "source_relation_uri": row["level2_uri"],
                "result": status,
            }
        )

    coverage_counts = Counter(row["result"] for row in coverage)
    provisional = [
        row for row in level1_candidates if row["inheritance_status"] == "PROVISIONAL_LEVEL1"
    ]
    summary: dict[str, object] = {
        "unresolved_source_relations": len(unresolved),
        "unresolved_by_source": dict(Counter(row["source"] for row in unresolved)),
        "eventkg_overlap_context_groups": len(eventkg_groups),
        "eventkg_unresolved_relations_with_overlap": len(
            {key[0] for key in eventkg_groups}
        ),
        "warsampo_unresolved_relations_with_overlap": len(war_groups),
        "level1_candidate_rows": len(level1_candidates),
        "provisional_level1_rows": len(provisional),
        "provisional_level1_relations": len(
            {(row["source"], row["source_relation_uri"]) for row in provisional}
        ),
        "coverage_results": dict(sorted(coverage_counts.items())),
        "classifier_run": False,
        "source_data_modified": False,
    }

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "eventkg_overlap_rankings.csv", eventkg_rankings)
    write_csv(OUT / "eventkg_group_decisions.csv", eventkg_decisions)
    write_csv(OUT / "warsampo_overlap_rankings.csv", warsampo_rankings)
    write_csv(OUT / "level1_candidates.csv", level1_candidates)
    write_csv(OUT / "unresolved_relation_coverage.csv", coverage)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report = f"""# QID-overlap Level 1 inheritance POC

Date: 2026-10-11

## Method

This POC starts with the **{len(unresolved):,} relations** that have no declared
ontology parent. It matches repeated QID endpoint pairs to Wikidata predicates,
tests same and reverse directions, and then reads the matched Wikidata
predicate's declared parent. It does not change a source relation or accept a
mapping from names alone.

EventKG uses graph, endpoint kind, and relation format as separate contexts.
Its existing name-blind score tests pair coverage, target stability, held-out
stability, and support. WarSampo uses the screened identity overlap and accepts
only at least 20 shared pairs with at least 90% WarSampo and 80% Wikidata
co-connected coverage.

## Result

- EventKG overlap reaches **{len({key[0] for key in eventkg_groups}):,} of 271**
  unresolved EventKG relations in **{len(eventkg_groups):,} contexts**.
- WarSampo overlap reaches **{len(war_groups):,} of 72** unresolved WarSampo
  relations.
- The run creates **{len(level1_candidates):,} inherited Level 1 candidate rows**.
- Only **{len(provisional):,} candidate row** for
  **{summary['provisional_level1_relations']:,} relation** passes the automatic
  evidence gate.

The accepted POC case is WarSampo `hasConflict` -> Wikidata `P607` in the same
direction, based on 115 shared pairs. Wikidata declares `P607` under `P1344`
(`participant in`), so `P1344` is a provisional inherited Level 1 value.

EventKG `hasWonPrize` strongly matches `P166` (`award received`) on 409 pairs,
but Wikidata does not declare a parent for `P166`. This produces a strong Level
2 alignment but no inherited Level 1 value.

WarSampo `hasUpperUnit` has three shared pairs with `P361` in the same direction
and `P527` in reverse. Both offer parent candidates, but three pairs are below
the evidence gate. They remain review candidates.

## Coverage result

| Result | Relations |
|---|---:|
{chr(10).join(f"| {status} | {count} |" for status, count in sorted(coverage_counts.items()))}

Wikidata's 307 unresolved properties are marked as the reference source. This
one-way POC cannot create a Wikidata parent when Wikidata itself declares none.

## Limits

- Missing overlap is not evidence that relations differ.
- EventKG facts copied from Wikidata were excluded from the overlap votes.
- WarSampo coverage is limited to identities that passed the earlier QID
  screening.
- An inherited Level 1 is a provisional cross-source mapping. It is not a new
  source ontology assertion.

## Files

- `eventkg_overlap_rankings.csv`: every observed EventKG-Wikidata candidate.
- `eventkg_group_decisions.csv`: the top result for each EventKG context.
- `warsampo_overlap_rankings.csv`: screened WarSampo-Wikidata candidates.
- `level1_candidates.csv`: inherited Wikidata parent options.
- `unresolved_relation_coverage.csv`: one result for each unresolved relation.
- `summary.json`: machine-readable totals.
"""
    REPORT.write_text(report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))

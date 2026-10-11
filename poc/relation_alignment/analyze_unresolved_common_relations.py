"""Describe unresolved source relations before any text classifier is built."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from run_data_driven_mapping_poc import GROUP_FIELDS, evidence_score, evidence_status

HERE = Path(__file__).resolve().parent
COMMON_MAP = HERE / "common_relation_map" / "common_relation_source_map.csv"
SOURCE_ONTOLOGY = (
    HERE / "source_ontology_map" / "source_ontology_level1_level2.csv"
)
FULL_MAP = HERE / "level1_level2_full_map" / "level1_level2_map.csv"
EVENTKG_CANDIDATES = (
    HERE / "mapping_discovery" / "eventkg_wikidata_candidates.csv"
)
WARSAMPO_CANDIDATES = HERE / "audit_2026-10-11" / "type_mapping_ranking.csv"
OUT = HERE / "unresolved_relation_eda"
REPORT = HERE / "UNRESOLVED_RELATION_EDA_2026-10-11.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def option_tier(row: dict[str, str], rank: int, margin: float) -> str:
    if (
        rank == 1
        and evidence_status(row) == "STRONG_CANDIDATE"
        and margin >= 15
    ):
        return "MERGE_GATE_WINNER"
    shared = int(row["shared_pairs"])
    if shared >= 5:
        return "SUPPORTED_REVIEW_OPTION"
    if shared >= 2:
        return "WEAK_REPEATED_OPTION"
    return "SINGLE_PAIR_ONLY"


def classify(options: list[dict[str, object]]) -> str:
    if not options:
        return "NO_QID_PAIR_OVERLAP"
    winners = [row for row in options if row["option_tier"] == "MERGE_GATE_WINNER"]
    winner_pairs = {
        (row["candidate_common_relation_id"], row["direction_to_candidate"])
        for row in winners
    }
    if len(winner_pairs) == 1:
        return "READY_SINGLE_TARGET"
    supported = [
        row
        for row in options
        if row["option_tier"]
        in {"MERGE_GATE_WINNER", "SUPPORTED_REVIEW_OPTION"}
    ]
    if not supported:
        return "LOW_SUPPORT_ONLY"
    directions: dict[object, set[object]] = defaultdict(set)
    for row in supported:
        directions[row["candidate_common_relation_id"]].add(
            row["direction_to_candidate"]
        )
    if any(len(values) > 1 for values in directions.values()):
        return "DIRECTION_AMBIGUITY"
    if len(directions) > 1:
        return "MULTIPLE_TARGETS"
    return "SINGLE_TARGET_BELOW_MERGE_GATE"


def build() -> dict[str, object]:
    source_rows = [
        row
        for row in read_csv(COMMON_MAP)
        if row["mapping_method"] == "SOURCE_NATIVE_ONLY"
    ]
    full_map = {
        row["canonical_level2_id"]: row for row in read_csv(FULL_MAP)
    }

    role_by_uri: dict[str, str] = {}
    for row in read_csv(SOURCE_ONTOLOGY):
        if row["source"] == "EventKG":
            role_by_uri[row["level2_uri"]] = row["source_predicate"]

    eventkg_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(EVENTKG_CANDIDATES):
        eventkg_groups[tuple(row[field] for field in GROUP_FIELDS)].append(row)

    war_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(WARSAMPO_CANDIDATES):
        war_groups[row["war_predicate"]].append(row)

    all_options: list[dict[str, object]] = []
    options_by_key: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)

    for source_row in source_rows:
        key = (source_row["source"], source_row["source_predicate"])
        if source_row["source"] == "EventKG":
            role = role_by_uri.get(source_row["source_predicate"], "")
            matching_groups = [
                (context, rows)
                for context, rows in eventkg_groups.items()
                if context[0] == role
            ]
            for context, candidates in matching_groups:
                ranked = sorted(
                    candidates,
                    key=lambda row: (
                        -evidence_score(row),
                        -int(row["shared_pairs"]),
                        row["wd_property"],
                        row["direction"],
                    ),
                )
                runner_score = evidence_score(ranked[1]) if len(ranked) > 1 else 0
                margin = round(evidence_score(ranked[0]) - runner_score, 1)
                context_text = "|".join(context[1:])
                for rank, candidate in enumerate(ranked, start=1):
                    common_id = f"wd:{candidate['wd_property']}"
                    metadata = full_map.get(common_id, {})
                    option = {
                        "source": "EventKG",
                        "source_predicate": source_row["source_predicate"],
                        "source_role": role,
                        "source_occurrence_count": source_row[
                            "source_occurrence_count"
                        ],
                        "source_level1_family": source_row["level1_family"],
                        "context": context_text,
                        "option_rank": rank,
                        "candidate_common_relation_id": common_id,
                        "candidate_label": metadata.get("level2_label", ""),
                        "direction_to_candidate": candidate["direction"],
                        "shared_pairs": candidate["shared_pairs"],
                        "pair_coverage_pct": candidate["pct_of_ek_co_connected"],
                        "held_out_pairs": candidate["test_pairs"],
                        "held_out_coverage_pct": candidate[
                            "test_pct_of_ek_co_connected"
                        ],
                        "evidence_score": evidence_score(candidate),
                        "evidence_status": evidence_status(candidate),
                        "option_tier": option_tier(candidate, rank, margin),
                        "target_level1_family": (
                            metadata.get("level1_family", "")
                            if metadata.get("assignment_status")
                            == "EXISTING_CATALOG_ASSIGNMENT"
                            else "UNRESOLVED"
                        ),
                        "target_level1_candidate": metadata.get(
                            "level1_family", ""
                        ),
                        "target_level1_assignment_status": metadata.get(
                            "assignment_status", ""
                        ),
                        "example_qid_pairs": candidate["example_qid_pairs"],
                    }
                    all_options.append(option)
                    options_by_key[key].append(option)
        else:
            candidates = sorted(
                war_groups.get(source_row["source_predicate"], []),
                key=lambda row: (
                    -int(row["shared_pairs"]),
                    row["wd_property"],
                    row["direction"],
                ),
            )
            for rank, candidate in enumerate(candidates, start=1):
                common_id = f"wd:{candidate['wd_property']}"
                metadata = full_map.get(common_id, {})
                shared = int(candidate["shared_pairs"])
                option = {
                    "source": "WarSampo",
                    "source_predicate": source_row["source_predicate"],
                    "source_role": source_row["source_predicate"].rsplit("/", 1)[-1],
                    "source_occurrence_count": source_row["source_occurrence_count"],
                    "source_level1_family": source_row["level1_family"],
                    "context": "screened QID endpoint pairs",
                    "option_rank": rank,
                    "candidate_common_relation_id": common_id,
                    "candidate_label": metadata.get("level2_label", ""),
                    "direction_to_candidate": candidate["direction"],
                    "shared_pairs": shared,
                    "pair_coverage_pct": candidate["pct_of_war_co_connected"],
                    "held_out_pairs": "",
                    "held_out_coverage_pct": "",
                    "evidence_score": min(
                        float(candidate["pct_of_war_co_connected"]),
                        float(candidate["pct_of_wd_co_connected"]),
                    ),
                    "evidence_status": "INSUFFICIENT_SUPPORT",
                    "option_tier": (
                        "SUPPORTED_REVIEW_OPTION"
                        if shared >= 5
                        else "WEAK_REPEATED_OPTION"
                        if shared >= 2
                        else "SINGLE_PAIR_ONLY"
                    ),
                    "target_level1_family": (
                        metadata.get("level1_family", "")
                        if metadata.get("assignment_status")
                        == "EXISTING_CATALOG_ASSIGNMENT"
                        else "UNRESOLVED"
                    ),
                    "target_level1_candidate": metadata.get("level1_family", ""),
                    "target_level1_assignment_status": metadata.get(
                        "assignment_status", ""
                    ),
                    "example_qid_pairs": "",
                }
                all_options.append(option)
                options_by_key[key].append(option)

    relation_rows: list[dict[str, object]] = []
    for source_row in source_rows:
        key = (source_row["source"], source_row["source_predicate"])
        options = options_by_key.get(key, [])
        supported = [
            row
            for row in options
            if row["option_tier"]
            in {"MERGE_GATE_WINNER", "SUPPORTED_REVIEW_OPTION"}
        ]
        weak = [row for row in options if row not in supported]
        relation_rows.append(
            {
                "source": source_row["source"],
                "source_predicate": source_row["source_predicate"],
                "source_label": source_row["common_relation_label"],
                "source_occurrence_count": source_row["source_occurrence_count"],
                "level1_family": source_row["level1_family"],
                "level1_candidate": source_row["level1_candidate"],
                "level1_assignment_status": source_row[
                    "level1_assignment_status"
                ],
                "eda_status": classify(options),
                "overlap_context_count": len({row["context"] for row in options}),
                "observed_option_rows": len(options),
                "observed_target_count": len(
                    {row["candidate_common_relation_id"] for row in options}
                ),
                "supported_target_count": len(
                    {row["candidate_common_relation_id"] for row in supported}
                ),
                "supported_level2_options": "|".join(
                    sorted(
                        {
                            str(row["candidate_common_relation_id"])
                            for row in supported
                        }
                    )
                ),
                "weak_observed_level2_options": "|".join(
                    sorted(
                        {str(row["candidate_common_relation_id"]) for row in weak}
                    )
                ),
                "observed_directions": "|".join(
                    sorted({str(row["direction_to_candidate"]) for row in options})
                ),
                "max_shared_pairs": max(
                    (int(row["shared_pairs"]) for row in options), default=0
                ),
            }
        )

    status_counts = Counter(str(row["eda_status"]) for row in relation_rows)
    status_occurrences: Counter[str] = Counter()
    for row in relation_rows:
        status_occurrences[str(row["eda_status"])] += int(
            row["source_occurrence_count"]
        )
    source_status = Counter(
        (str(row["source"]), str(row["eda_status"])) for row in relation_rows
    )
    tier_counts = Counter(str(row["option_tier"]) for row in all_options)
    summary: dict[str, object] = {
        "unresolved_source_relation_rows": len(relation_rows),
        "unresolved_by_source": dict(Counter(row["source"] for row in relation_rows)),
        "eda_status_counts": dict(sorted(status_counts.items())),
        "eda_status_source_occurrence_sums": dict(sorted(status_occurrences.items())),
        "status_by_source": {
            f"{source}|{status}": count
            for (source, status), count in sorted(source_status.items())
        },
        "observed_candidate_option_rows": len(all_options),
        "option_tier_counts": dict(sorted(tier_counts.items())),
        "relations_with_supported_options": sum(
            int(row["supported_target_count"]) > 0 for row in relation_rows
        ),
        "classifier_run": False,
        "source_data_modified": False,
    }

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "unresolved_relation_summary.csv", relation_rows)
    write_csv(OUT / "observed_candidate_options.csv", all_options)
    write_csv(
        OUT / "supported_candidate_options.csv",
        [
            row
            for row in all_options
            if row["option_tier"]
            in {"MERGE_GATE_WINNER", "SUPPORTED_REVIEW_OPTION"}
        ],
    )
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    report = f"""# EDA of unresolved common relations

Date: 2026-10-11

## Result

The common map has **{len(relation_rows):,} source predicate rows** without an
accepted cross-source Level 2 mapping. This EDA uses their saved QID-pair
overlap and stops before text classification.

| EDA status | Source predicates | Source occurrence sum |
|---|---:|---:|
{chr(10).join(f"| {status} | {status_counts[status]:,} | {status_occurrences[status]:,} |" for status in sorted(status_counts))}

`Source occurrence sum` counts source records. It is not a count of unique
facts or entities.

**{summary['relations_with_supported_options']:,} predicates** have at least
one supported target option.

## Coverage by source

| Source | No overlap | Low support | One target below gate | Multiple targets | Direction ambiguity |
|---|---:|---:|---:|---:|---:|
| EventKG | {source_status[('EventKG', 'NO_QID_PAIR_OVERLAP')]:,} | {source_status[('EventKG', 'LOW_SUPPORT_ONLY')]:,} | {source_status[('EventKG', 'SINGLE_TARGET_BELOW_MERGE_GATE')]:,} | {source_status[('EventKG', 'MULTIPLE_TARGETS')]:,} | {source_status[('EventKG', 'DIRECTION_AMBIGUITY')]:,} |
| WarSampo | {source_status[('WarSampo', 'NO_QID_PAIR_OVERLAP')]:,} | {source_status[('WarSampo', 'LOW_SUPPORT_ONLY')]:,} | {source_status[('WarSampo', 'SINGLE_TARGET_BELOW_MERGE_GATE')]:,} | {source_status[('WarSampo', 'MULTIPLE_TARGETS')]:,} | {source_status[('WarSampo', 'DIRECTION_AMBIGUITY')]:,} |

## Option tiers

| Evidence tier | Candidate rows |
|---|---:|
{chr(10).join(f"| {tier} | {count:,} |" for tier, count in sorted(tier_counts.items()))}

- `SUPPORTED_REVIEW_OPTION`: at least five repeated QID endpoint pairs.
- `WEAK_REPEATED_OPTION`: two to four pairs.
- `SINGLE_PAIR_ONLY`: one pair.
- `MERGE_GATE_WINNER`: passes the complete automatic merge gate.

## Status meaning

- `NO_QID_PAIR_OVERLAP`: the local data has no shared QID endpoint pair for
  this source predicate.
- `LOW_SUPPORT_ONLY`: overlap exists, but every option has fewer than five
  repeated pairs.
- `SINGLE_TARGET_BELOW_MERGE_GATE`: one supported target exists, but it does
  not pass the complete automatic gate.
- `MULTIPLE_TARGETS`: at least two supported Wikidata relation targets exist.
- `DIRECTION_AMBIGUITY`: one target is observed in both directions with at
  least five pairs.
- `READY_SINGLE_TARGET`: one target and direction pass the merge gate.

## Next decision

Review the supported options. Use them as the first classifier choice list only
after confirming that the list has acceptable coverage. Keep weak options as
diagnostic evidence. Predicates with no overlap need more linked data or a
different candidate source.

## Files

- `unresolved_relation_summary.csv`: one row per unresolved source predicate.
- `supported_candidate_options.csv`: repeated options for review.
- `observed_candidate_options.csv`: every observed option, including weak ones.
- `summary.json`: counts and validation flags.
"""
    REPORT.write_text(report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))

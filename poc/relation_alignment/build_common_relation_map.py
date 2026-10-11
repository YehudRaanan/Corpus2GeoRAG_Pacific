"""Build one provisional cross-source relation map from endpoint overlap."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from run_data_driven_mapping_poc import GROUP_FIELDS, evidence_score, evidence_status

HERE = Path(__file__).resolve().parent
SOURCE_ALIGNMENT = HERE / "relation_catalog_eda" / "source_alignment.csv"
SOURCE_ONTOLOGY = (
    HERE / "source_ontology_map" / "source_ontology_level1_level2.csv"
)
FULL_MAP = HERE / "level1_level2_full_map" / "level1_level2_map.csv"
EVENTKG_CANDIDATES = (
    HERE / "mapping_discovery" / "eventkg_wikidata_candidates.csv"
)
WARSAMPO_CANDIDATES = HERE / "audit_2026-10-11" / "type_mapping_ranking.csv"
OUT = HERE / "common_relation_map"
REPORT = HERE / "COMMON_RELATION_MAP_2026-10-11.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def accepted_eventkg_contexts(
    candidates: list[dict[str, str]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        grouped[tuple(row[field] for field in GROUP_FIELDS)].append(row)

    accepted = []
    for context, rows in sorted(grouped.items()):
        ranked = sorted(
            rows,
            key=lambda row: (
                -evidence_score(row),
                -int(row["shared_pairs"]),
                row["wd_property"],
                row["direction"],
            ),
        )
        top = ranked[0]
        runner_score = evidence_score(ranked[1]) if len(ranked) > 1 else 0.0
        margin = round(evidence_score(top) - runner_score, 1)
        if evidence_status(top) != "STRONG_CANDIDATE" or margin < 15:
            continue
        accepted.append(
            {
                **dict(zip(GROUP_FIELDS, context, strict=True)),
                "wd_property": top["wd_property"],
                "direction": top["direction"],
                "shared_pairs": int(top["shared_pairs"]),
                "evidence_score": evidence_score(top),
                "score_margin": margin,
                "example_qid_pairs": top["example_qid_pairs"],
            }
        )
    return accepted


def accepted_warsampo_relations(
    candidates: list[dict[str, str]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        grouped[row["war_predicate"]].append(row)

    accepted = []
    for predicate, rows in sorted(grouped.items()):
        ranked = sorted(
            rows,
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
        if not (
            int(top["shared_pairs"]) >= 20
            and float(top["pct_of_war_co_connected"]) >= 90
            and float(top["pct_of_wd_co_connected"]) >= 80
        ):
            continue
        accepted.append(
            {
                "source_relation_uri": predicate,
                "wd_property": top["wd_property"],
                "direction": top["direction"],
                "shared_pairs": int(top["shared_pairs"]),
                "evidence_score": min(
                    float(top["pct_of_war_co_connected"]),
                    float(top["pct_of_wd_co_connected"]),
                ),
                "score_margin": "",
                "context": "screened QID endpoint pairs",
                "example_qid_pairs": "",
            }
        )
    return accepted


def build() -> dict[str, object]:
    alignment = read_csv(SOURCE_ALIGNMENT)
    source_ontology = read_csv(SOURCE_ONTOLOGY)
    full_map = {
        row["canonical_level2_id"]: row for row in read_csv(FULL_MAP)
    }
    alignment_by_key = {
        (row["source"], row["source_predicate"]): row for row in alignment
    }

    role_uris: dict[str, set[str]] = defaultdict(set)
    for row in source_ontology:
        if row["source"] == "EventKG":
            role_uris[row["source_predicate"]].add(row["level2_uri"])

    evidence_rows: list[dict[str, object]] = []
    accepted_by_relation: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in accepted_eventkg_contexts(read_csv(EVENTKG_CANDIDATES)):
        uris = role_uris[row["ek_role"]]
        if len(uris) != 1:
            continue
        source_uri = next(iter(uris))
        evidence = {
            "source": "EventKG",
            "source_predicate": source_uri,
            "source_role": row["ek_role"],
            "context": "|".join(str(row[field]) for field in GROUP_FIELDS[1:]),
            "candidate_common_relation_id": f"wd:{row['wd_property']}",
            "direction_to_common": row["direction"],
            "shared_pairs": row["shared_pairs"],
            "evidence_score": row["evidence_score"],
            "score_margin": row["score_margin"],
            "example_qid_pairs": row["example_qid_pairs"],
        }
        evidence_rows.append(evidence)
        accepted_by_relation[("EventKG", source_uri)].append(evidence)

    for row in accepted_warsampo_relations(read_csv(WARSAMPO_CANDIDATES)):
        evidence = {
            "source": "WarSampo",
            "source_predicate": row["source_relation_uri"],
            "source_role": row["source_relation_uri"].rsplit("/", 1)[-1],
            "context": row["context"],
            "candidate_common_relation_id": f"wd:{row['wd_property']}",
            "direction_to_common": row["direction"],
            "shared_pairs": row["shared_pairs"],
            "evidence_score": row["evidence_score"],
            "score_margin": row["score_margin"],
            "example_qid_pairs": row["example_qid_pairs"],
        }
        evidence_rows.append(evidence)
        accepted_by_relation[("WarSampo", row["source_relation_uri"])].append(evidence)

    decisions: dict[tuple[str, str], dict[str, object]] = {}
    for key, rows in sorted(accepted_by_relation.items()):
        targets = {
            (str(row["candidate_common_relation_id"]), str(row["direction_to_common"]))
            for row in rows
        }
        current = alignment_by_key.get(key)
        if current is None or len(targets) != 1:
            action = "KEEP_UNRESOLVED"
            target = ""
            direction = ""
        else:
            target, direction = next(iter(targets))
            if current["canonical_level2_id"] == target and current["direction"] == direction:
                action = "CONFIRMS_EXISTING_MAPPING"
            elif current["mapping_status"] == "SOURCE_ONLY":
                action = "NEW_PROVISIONAL_COMMON_MAPPING"
            else:
                action = "EXISTING_MAPPING_PRESERVED_FOR_REVIEW"
        decisions[key] = {
            "action": action,
            "target": target,
            "direction": direction,
            "contexts": len(rows),
            "shared_pairs_sum": sum(int(row["shared_pairs"]) for row in rows),
            "shared_pairs_max": max(int(row["shared_pairs"]) for row in rows),
            "context_values": ";".join(sorted(str(row["context"]) for row in rows)),
        }

    common_rows: list[dict[str, object]] = []
    for row in alignment:
        key = (row["source"], row["source_predicate"])
        decision = decisions.get(key)
        common_id = row["canonical_level2_id"]
        direction = row["direction"]
        mapping_status = row["mapping_status"]
        if decision and decision["action"] == "NEW_PROVISIONAL_COMMON_MAPPING":
            common_id = str(decision["target"])
            direction = str(decision["direction"])
            mapping_status = "OBSERVATION_SUPPORTED_PROVISIONAL"

        metadata = full_map[common_id]
        accepted_level1 = (
            metadata["level1_family"]
            if metadata["assignment_status"] == "EXISTING_CATALOG_ASSIGNMENT"
            else "UNRESOLVED"
        )
        if mapping_status == "SOURCE_ONLY":
            method = "SOURCE_NATIVE_ONLY"
            review = "UNRESOLVED_CROSS_SOURCE"
        elif mapping_status == "OBSERVATION_SUPPORTED_PROVISIONAL":
            method = "OBSERVATION_OVERLAP"
            review = "PROVISIONAL"
        elif mapping_status == "EXACT_DATA_SUPPORTED":
            method = "EXISTING_OBSERVATION_MAPPING"
            review = "ACCEPTED"
        elif row["source"] == "Wikidata" or "wikidata.org/prop/direct/" in row["source_predicate"]:
            method = "NATIVE_OR_REUSED_WIKIDATA_ID"
            review = "ACCEPTED"
        else:
            method = "EXISTING_CATALOG_MAPPING"
            review = "ACCEPTED"

        common_rows.append(
            {
                "source": row["source"],
                "source_predicate": row["source_predicate"],
                "common_relation_id": common_id,
                "common_relation_label": metadata["level2_label"],
                "direction_to_common": direction,
                "mapping_status": mapping_status,
                "mapping_method": method,
                "mapping_review_status": review,
                "level1_family": accepted_level1,
                "level1_candidate": metadata["level1_family"],
                "level1_assignment_status": metadata["assignment_status"],
                "source_occurrence_count": row["occurrence_count"],
                "observation_contexts": decision["contexts"] if decision else 0,
                "observation_shared_pairs_max": decision["shared_pairs_max"] if decision else 0,
                "observation_shared_pairs_sum": decision["shared_pairs_sum"] if decision else 0,
                "observation_context_values": decision["context_values"] if decision else "",
            }
        )

    for evidence in evidence_rows:
        decision = decisions[(str(evidence["source"]), str(evidence["source_predicate"]))]
        evidence["map_action"] = decision["action"]

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in common_rows:
        grouped[str(row["common_relation_id"])].append(row)
    group_rows = []
    for common_id, members in sorted(grouped.items()):
        group_rows.append(
            {
                "common_relation_id": common_id,
                "common_relation_label": members[0]["common_relation_label"],
                "level1_family": members[0]["level1_family"],
                "level1_candidate": members[0]["level1_candidate"],
                "level1_assignment_status": members[0]["level1_assignment_status"],
                "sources": "|".join(sorted({str(row["source"]) for row in members})),
                "source_count": len({str(row["source"]) for row in members}),
                "source_predicate_count": len(members),
                "source_predicates": "|".join(
                    sorted(str(row["source_predicate"]) for row in members)
                ),
                "source_occurrence_sum": sum(
                    int(row["source_occurrence_count"]) for row in members
                ),
                "has_provisional_mapping": any(
                    row["mapping_review_status"] == "PROVISIONAL" for row in members
                ),
            }
        )

    action_counts = Counter(str(row["action"]) for row in decisions.values())
    source_count_groups = Counter(int(row["source_count"]) for row in group_rows)
    summary: dict[str, object] = {
        "input_source_relation_rows": len(alignment),
        "input_common_relation_ids": len(
            {row["canonical_level2_id"] for row in alignment}
        ),
        "accepted_observation_contexts": len(evidence_rows),
        "observation_supported_source_relations": len(decisions),
        "observation_actions": dict(sorted(action_counts.items())),
        "new_provisional_source_mappings": action_counts[
            "NEW_PROVISIONAL_COMMON_MAPPING"
        ],
        "output_source_relation_rows": len(common_rows),
        "output_common_relation_ids": len(group_rows),
        "common_relations_by_source_count": {
            str(count): total for count, total in sorted(source_count_groups.items())
        },
        "multi_source_common_relation_ids": sum(
            total for count, total in source_count_groups.items() if count > 1
        ),
        "common_ids_reduced_by": len(
            {row["canonical_level2_id"] for row in alignment}
        )
        - len(group_rows),
        "level1_unresolved_source_rows": sum(
            row["level1_family"] == "UNRESOLVED" for row in common_rows
        ),
        "source_data_modified": False,
    }

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "common_relation_source_map.csv", common_rows)
    write_csv(OUT / "common_relation_groups.csv", group_rows)
    write_csv(OUT / "observation_mapping_evidence.csv", evidence_rows)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    new_mappings = [
        (key, value)
        for key, value in decisions.items()
        if value["action"] == "NEW_PROVISIONAL_COMMON_MAPPING"
    ]
    report = f"""# Common relation map from observation overlap

Date: 2026-10-11

## Result

The map keeps all **{len(common_rows):,} source relation rows** and groups them
under **{len(group_rows):,} common Level 2 relation IDs**. The earlier map had
**{summary['input_common_relation_ids']:,} IDs**. Observation overlap added
**{len(new_mappings):,}** provisional source-to-common mappings and reduced the
common ID count by **{summary['common_ids_reduced_by']:,}**.

No source relation or source data was changed. Direction stays explicit.

Of the common IDs, **{summary['multi_source_common_relation_ids']:,}** connect
more than one source: **{source_count_groups[2]:,}** connect two sources and
**{source_count_groups[3]:,}** connect all three sources.

## New provisional mappings

| Source predicate | Common Level 2 | Direction | Max shared pairs | Contexts |
|---|---|---|---:|---:|
{chr(10).join(f"| `{key[1]}` | `{value['target']}` | {value['direction']} | {value['shared_pairs_max']:,} | {value['contexts']} |" for key, value in new_mappings)}

## Decision rule

1. Use repeated pairs whose endpoints have the same Wikidata IDs.
2. Keep only context winners with at least 20 shared pairs, at least five held-out
   pairs, at least five targets, 90% pair coverage, 80% coverage after the
   largest target, and 80% held-out coverage.
3. Require a score lead of at least 15 points over the next candidate.
4. Merge a source predicate only when all accepted contexts select the same
   Wikidata relation and direction.
5. Preserve an existing mapping when the observation winner points elsewhere.
   Record that result for review instead of replacing it.

## Important limits

- A provisional mapping is strong repeated-use evidence. It is not proof that
  the source definitions are identical in every context.
- Source occurrence sums can contain the same fact in more than one source.
- A missing overlap keeps the source relation separate.
- Level 1 stays `UNRESOLVED` when the full map has only a ranked Level 1 option.

## Files

- `common_relation_source_map.csv`: every source predicate and its common ID.
- `common_relation_groups.csv`: one row per common Level 2 ID.
- `observation_mapping_evidence.csv`: accepted observation contexts and actions.
- `summary.json`: validation totals.
"""
    REPORT.write_text(report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))

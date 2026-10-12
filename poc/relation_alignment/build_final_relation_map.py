"""Consolidate all relation-alignment decisions into one final catalog."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_MAP = HERE / "common_relation_map" / "common_relation_source_map.csv"
AUDIT_DIR = HERE / "eventkg_wikidata_declared_mapping_audit"
AUDIT = AUDIT_DIR / "predicate_audit.csv"
CANDIDATES = AUDIT_DIR / "mapping_candidates.csv"
RESOLUTIONS = AUDIT_DIR / "conflict_broader_resolutions.csv"
INDEPENDENT = HERE / "unresolved_relation_examples" / "relation_example_coverage.csv"
OUT = HERE / "final_relation_map"
REPORT = HERE / "FINAL_RELATION_MAP_2026-10-12.md"
RELATION_MAP_VERSION = "relation-map-v1.0.0"
DELIVERY_TABLE = HERE.parent.parent / "deliveries" / "RELATION_MAPPING_TABLE_v1.0.0.csv"

RUNTIME_RULES = {
    "EventKG": {
        "time_from_input": "sem:hasBeginTimeStamp",
        "time_to_input": "sem:hasEndTimeStamp",
        "time_point_input": "",
        "time_join_rule": "READ_REIFIED_RELATION",
        "evidence_requirements": "relation_uri|named_graph|source_uri|raw_time_values",
    },
    "WarSampo": {
        "time_from_input": ("crm:P4_has_time-span->crm:P82a_begin_of_the_begin"),
        "time_to_input": "crm:P4_has_time-span->crm:P82b_end_of_the_end",
        "time_point_input": "",
        "time_join_rule": "FOLLOW_P4_TIME_SPAN",
        "evidence_requirements": (
            "assertion_or_activity_uri|named_graph|source_uri|time_span_uri|raw_time_values"
        ),
    },
    "Wikidata": {
        "time_from_input": "qualifiers.P580",
        "time_to_input": "qualifiers.P582",
        "time_point_input": "qualifiers.P585",
        "time_join_rule": "READ_STATEMENT_QUALIFIERS",
        "evidence_requirements": "statement_id|references|qualifiers|rank|raw_time_values",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def common_id(value: str) -> str:
    return f"wd:{value}" if re.fullmatch(r"P\d+", value) else value


def runtime_fields(
    source: str, final_relation_id: str, review_status: str
) -> dict[str, object]:
    if source == "WarSampo":
        priority = (
            1
            if final_relation_id.startswith("wd:") and review_status == "ACCEPTED"
            else 2
        )
    elif source == "EventKG":
        priority = 3
    else:
        assert source == "Wikidata"
        priority = 4

    return {
        "selection_priority": priority,
        **RUNTIME_RULES[source],
        "evidence_policy": "PRESERVE_ALL_SUPPORTING_ASSERTIONS",
        "time_conflict_policy": "SELECTED_ASSERTION_VALUE_KEEP_ALL_CONFLICTS",
        "relation_map_version": RELATION_MAP_VERSION,
    }


def build() -> dict[str, object]:
    base_rows = read_csv(BASE_MAP)
    audit_rows = read_csv(AUDIT)
    candidate_rows = read_csv(CANDIDATES)
    resolution_rows = read_csv(RESOLUTIONS)
    independent_rows = read_csv(INDEPENDENT)

    eventkg_base = {
        row["source_predicate"]: row for row in base_rows if row["source"] == "EventKG"
    }
    assert len(eventkg_base) == sum(row["source"] == "EventKG" for row in base_rows)

    labels_by_common_id = {
        row["common_relation_id"]: row["common_relation_label"] for row in base_rows
    }
    metadata_by_common_id = {
        row["common_relation_id"]: row
        for row in base_rows
        if row["source"] == "Wikidata"
    }
    candidates_by_predicate: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        candidates_by_predicate[row["eventkg_predicate"]].append(row)

    decisions: dict[str, dict[str, str]] = {}
    for row in audit_rows:
        predicate = row["eventkg_predicate"]
        status = row["audit_status"]
        if status == "DECLARED_EXACT_SINGLE":
            target = row["exact_wikidata_options"]
            matches = [
                item
                for item in candidates_by_predicate[predicate]
                if item["wikidata_property"] == target
            ]
            assert matches and {item["direction"] for item in matches} == {"same"}
            decisions[predicate] = {
                "id": common_id(target),
                "label": next(
                    (
                        item["wikidata_label"]
                        for item in matches
                        if item["wikidata_label"]
                    ),
                    labels_by_common_id.get(common_id(target), target),
                ),
                "direction": "same",
                "class": "PUBLIC_DECLARED_EXACT",
                "review": "ACCEPTED",
                "evidence": " | ".join(
                    sorted({item["mapping_path"] for item in matches})
                ),
            }
        elif status == "AUTOMATIC_ALIGNMENT_CANDIDATE":
            target = row["automatic_options"]
            matches = [
                item
                for item in candidates_by_predicate[predicate]
                if item["wikidata_property"] == target
            ]
            assert matches and {item["direction"] for item in matches} == {"same"}
            decisions[predicate] = {
                "id": common_id(target),
                "label": next(item["wikidata_label"] for item in matches),
                "direction": "same",
                "class": "AUTOMATIC_ALIGNMENT",
                "review": "PROVISIONAL",
                "evidence": " | ".join(
                    sorted({item["mapping_path"] for item in matches})
                ),
            }

    for row in resolution_rows:
        predicate = row["eventkg_predicate"]
        target = common_id(row["canonical_level2_id"])
        decisions[predicate] = {
            "id": target,
            "label": (
                labels_by_common_id.get(target)
                or eventkg_base[predicate]["common_relation_label"]
            ),
            "direction": "same",
            "class": row["resolution"],
            "review": "ACCEPTED",
            "evidence": f"{row['public_mapping_path']}; {row['observed_endpoint_evidence']}",
        }

    for row in independent_rows:
        predicate = row["source_predicate"]
        assert row["level2_decision"] == "KEEP_INDEPENDENT_SOURCE_LEVEL2"
        decisions[predicate] = {
            "id": row["independent_level2_id"],
            "label": row["source_label"],
            "direction": "same",
            "class": "INDEPENDENT_NO_PUBLIC_MAPPING",
            "review": "ACCEPTED",
            "evidence": "No declared public cross-source mapping found; source relation retained",
        }

    audited = {row["eventkg_predicate"] for row in audit_rows}
    assert audited == set(decisions)
    assert audited <= set(eventkg_base)

    final_rows: list[dict[str, object]] = []
    for base in base_rows:
        decision = (
            decisions.get(base["source_predicate"])
            if base["source"] == "EventKG"
            else None
        )
        if decision:
            final_id = decision["id"]
            target_metadata = metadata_by_common_id.get(final_id)
            level1 = target_metadata or base
            final_class = decision["class"]
            review = decision["review"]
            evidence = decision["evidence"]
            label = decision["label"]
            direction = decision["direction"]
        else:
            final_id = base["common_relation_id"]
            label = base["common_relation_label"]
            direction = base["direction_to_common"]
            level1 = base
            if base["mapping_status"] == "SOURCE_ONLY":
                final_class = "INDEPENDENT_EXISTING_SOURCE_ONLY"
                review = "ACCEPTED"
                evidence = "No accepted cross-source mapping; source relation retained"
            else:
                final_class = base["mapping_method"]
                review = base["mapping_review_status"]
                evidence = "Existing common-map decision"

        final_rows.append(
            {
                "source": base["source"],
                "source_predicate": base["source_predicate"],
                "source_occurrence_count": base["source_occurrence_count"],
                "final_relation_id": final_id,
                "final_relation_label": label,
                "direction_to_final": direction,
                "final_mapping_class": final_class,
                "final_review_status": review,
                "level1_family": level1["level1_family"],
                "level1_candidate": level1["level1_candidate"],
                "level1_assignment_status": level1["level1_assignment_status"],
                "decision_evidence": evidence,
                "prior_common_relation_id": base["common_relation_id"],
                "source_data_modified": False,
                **runtime_fields(base["source"], final_id, review),
            }
        )

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in final_rows:
        grouped[str(row["final_relation_id"])].append(row)
    group_rows: list[dict[str, object]] = []
    for relation_id, members in sorted(grouped.items()):
        group_rows.append(
            {
                "final_relation_id": relation_id,
                "final_relation_label": members[0]["final_relation_label"],
                "level1_families": "|".join(
                    sorted({str(row["level1_family"]) for row in members})
                ),
                "sources": "|".join(sorted({str(row["source"]) for row in members})),
                "source_count": len({str(row["source"]) for row in members}),
                "source_predicate_count": len(members),
                "source_predicates": "|".join(
                    sorted(str(row["source_predicate"]) for row in members)
                ),
                "source_occurrence_sum": sum(
                    int(row["source_occurrence_count"]) for row in members
                ),
                "mapping_classes": "|".join(
                    sorted({str(row["final_mapping_class"]) for row in members})
                ),
                "review_statuses": "|".join(
                    sorted({str(row["final_review_status"]) for row in members})
                ),
            }
        )

    decision_rows = [
        row
        for row in final_rows
        if row["source"] == "EventKG" and row["source_predicate"] in audited
    ]
    class_counts = Counter(str(row["final_mapping_class"]) for row in decision_rows)
    review_counts = Counter(str(row["final_review_status"]) for row in final_rows)
    assert len(final_rows) == len(base_rows) == 1520
    assert len(decision_rows) == 217
    assert class_counts == {
        "PUBLIC_DECLARED_EXACT": 43,
        "AUTOMATIC_ALIGNMENT": 4,
        "ACCEPT_SCOPED_BROADER": 3,
        "ACCEPT_ONE_REJECT_ONE": 2,
        "ACCEPT_COMBINED": 1,
        "INDEPENDENT_NO_PUBLIC_MAPPING": 164,
    }
    assert all(row["final_relation_id"] for row in final_rows)
    assert len({(row["source"], row["source_predicate"]) for row in final_rows}) == 1520
    priority_counts = Counter(int(row["selection_priority"]) for row in final_rows)
    assert priority_counts == {1: 4, 2: 107, 3: 808, 4: 601}
    assert all(
        row["relation_map_version"] == RELATION_MAP_VERSION for row in final_rows
    )
    assert all(row["time_from_input"] and row["time_to_input"] for row in final_rows)

    by_source_predicate = {
        (str(row["source"]), str(row["source_predicate"])): row for row in final_rows
    }
    sample_checks = {
        (
            "WarSampo",
            "http://ldf.fi/schema/warsa/actors/hasConflict",
        ): (1, "wd:P607", "FOLLOW_P4_TIME_SPAN"),
        (
            "WarSampo",
            "http://ldf.fi/ammo/coo1980/socioeconomic_status",
        ): (
            2,
            "http://ldf.fi/ammo/coo1980/socioeconomic_status",
            "FOLLOW_P4_TIME_SPAN",
        ),
        (
            "EventKG",
            "http://dbpedia.org/ontology/affiliation",
        ): (3, "wd:P1416", "READ_REIFIED_RELATION"),
        ("Wikidata", "wd:P1000"): (4, "wd:P1000", "READ_STATEMENT_QUALIFIERS"),
    }
    for key, expected in sample_checks.items():
        row = by_source_predicate[key]
        actual = (
            int(row["selection_priority"]),
            row["final_relation_id"],
            row["time_join_rule"],
        )
        assert actual == expected, (key, actual, expected)

    summary: dict[str, object] = {
        "relation_map_version": RELATION_MAP_VERSION,
        "source_relation_rows": len(final_rows),
        "final_relation_ids": len(group_rows),
        "multi_source_relation_ids": sum(
            int(row["source_count"]) > 1 for row in group_rows
        ),
        "audited_eventkg_relations": len(decision_rows),
        "audited_decision_counts": dict(sorted(class_counts.items())),
        "all_rows_review_status_counts": dict(sorted(review_counts.items())),
        "selection_priority_counts": dict(sorted(priority_counts.items())),
        "runtime_sample_checks": len(sample_checks),
        "runtime_table_ready": True,
        "source_data_modified": False,
    }

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "final_relation_source_map.csv", final_rows)
    write_csv(DELIVERY_TABLE, final_rows)
    write_csv(OUT / "final_relation_groups.csv", group_rows)
    write_csv(OUT / "audited_eventkg_decisions.csv", decision_rows)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    mapped = [
        row
        for row in decision_rows
        if row["final_mapping_class"] != "INDEPENDENT_NO_PUBLIC_MAPPING"
    ]
    table = "\n".join(
        f"| `{row['source_predicate']}` | `{row['final_relation_id']}` | "
        f"{row['final_mapping_class']} | {row['final_review_status']} |"
        for row in mapped
    )
    report = f"""# Final relation mapping catalog

Date: 2026-10-12

## Result

The catalog contains **{len(final_rows):,} source relation rows** grouped under
**{len(group_rows):,} final Level 2 IDs**. It preserves the original source
predicates and direction.

The final audit decisions cover **217 EventKG relations**:

- 43 public declared exact mappings
- 6 reviewed scoped, conflict, or combined mappings
- 4 automatic mappings kept as provisional
- 164 source relations kept as independent Level 2 relations

## Cross-source decisions added by the final audit

| EventKG source predicate | Final Level 2 ID | Decision | Status |
|---|---|---|---|
{table}

## Independent relations

The 164 relations with no declared public mapping keep their source predicate
URI as the final Level 2 ID. Their examples and coverage remain in
`unresolved_relation_examples/`.

## Files

- `final_relation_map/final_relation_source_map.csv`: every source relation,
  selection priority, time join rule, evidence policy, conflict policy, and map
  version
- `final_relation_map/final_relation_groups.csv`: one row per final Level 2 ID
- `final_relation_map/audited_eventkg_decisions.csv`: the 217 final audit decisions
- `final_relation_map/summary.json`: validation counts

The source data was not changed.
"""
    REPORT.write_text(report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))

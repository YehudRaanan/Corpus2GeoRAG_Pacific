"""Build Relation Mapping Table v2 from the deterministic audit outputs.

Level 2 changes use identifier equality or saved formal mapping evidence only.
Level 1 remains a separate optional search view. Reverse relations are query
rewrite rules; this builder does not create duplicate graph edges.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DETERMINISTIC = HERE / "deterministic_level2_mapping"
INVENTORY = HERE / "relation_catalog_eda" / "source_predicate_inventory.csv"
REGISTRY = DETERMINISTIC / "deterministic_relation_registry.csv"
CONNECTIONS = DETERMINISTIC / "deterministic_connections.csv"
FORMAL_EVIDENCE = DETERMINISTIC / "formal_mapping_evidence.csv"
SAME_ID_VALIDATION = DETERMINISTIC / "same_identifier_pair_validation.csv"
V1 = ROOT / "GG_Data" / "mapping" / "RELATION_MAPPING_TABLE_v1.0.0.csv"
OUT = ROOT / "GG_Data" / "mapping"

ACCEPTED_STATUSES = {
    "READY_DETERMINISTIC_TRANSLATION",
    "TRANSLATION_VALID_ASSERTION_QA_REQUIRED",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def joined(values: set[str]) -> str:
    return "|".join(sorted(value for value in values if value))


def connection_id(key: tuple[str, str, str]) -> str:
    return hashlib.sha256("|".join(key).encode()).hexdigest()[:12]


def connection_decision(row: dict[str, str]) -> str:
    if row["left_relation"] == row["right_relation"]:
        return "ACCEPT_SAME_CODE_IDENTITY"
    return {
        "READY_DETERMINISTIC_TRANSLATION": "ACCEPT_FORMAL_TRANSLATION",
        "TRANSLATION_VALID_ASSERTION_QA_REQUIRED": (
            "ACCEPT_FORMAL_TRANSLATION_ASSERTION_QA_REQUIRED"
        ),
        "KEEP_SEPARATE_OPTIONAL_BROADER_VIEW": (
            "KEEP_SEPARATE_OPTIONAL_LEVEL1_SEARCH_VIEW"
        ),
        "BLOCKED_FORMAL_COMPONENT_CONFLICT": (
            "BLOCK_FORMAL_TRANSLATION_COMPONENT_CONFLICT"
        ),
        "BLOCKED_SEMANTIC_CONTRADICTION": (
            "BLOCK_FORMAL_TRANSLATION_SEMANTIC_CONTRADICTION"
        ),
    }[row["activation_status"]]


def build() -> dict[str, object]:
    registry = read_csv(REGISTRY)
    connections = read_csv(CONNECTIONS)
    formal_evidence = read_csv(FORMAL_EVIDENCE)
    inventory = [
        row for row in read_csv(INVENTORY) if row["eligibility"] == "LEVEL2_CANDIDATE"
    ]
    v1_rows = read_csv(V1)
    same_validation = {row["relation_id"]: row for row in read_csv(SAME_ID_VALIDATION)}

    assert len(registry) == len(inventory) == len(v1_rows) == 1520

    inventory_by_source_predicate = {
        (row["source"], row["source_predicate"]): row for row in inventory
    }
    v1_by_uri = {(row["source"], row["source_predicate"]): row for row in v1_rows}
    registry_by_key = {
        (row["source"], row["normalized_relation"]): row for row in registry
    }
    assert len(registry_by_key) == 1520

    row_context: dict[tuple[str, str], dict[str, str]] = {}
    for row in registry:
        inventory_row = inventory_by_source_predicate[
            (row["source"], row["source_predicate"])
        ]
        old_row = v1_by_uri[(row["source"], inventory_row["predicate_uri"])]
        row_context[(row["source"], row["normalized_relation"])] = {
            **row,
            "source_predicate_uri": inventory_row["predicate_uri"],
            "old_level1_family": old_row["level1_family"],
            "old_level1_candidate": old_row["level1_candidate"],
            "old_level1_status": old_row["level1_assignment_status"],
            "time_from_input": old_row["time_from_input"],
            "time_to_input": old_row["time_to_input"],
            "time_point_input": old_row["time_point_input"],
            "time_join_rule": old_row["time_join_rule"],
            "evidence_requirements": old_row["evidence_requirements"],
            "evidence_policy": old_row["evidence_policy"],
            "time_conflict_policy": old_row["time_conflict_policy"],
        }

    grouped_connections: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(
        list
    )
    for row in connections:
        grouped_connections[
            (row["left_relation"], row["right_relation"], row["direction"])
        ].append(row)
    assert len(grouped_connections) == 589

    symmetric_relations = {
        row["left_relation"]
        for row in formal_evidence
        if row["formal_relation"] == "SYMMETRIC"
        and row["left_relation"] == row["right_relation"]
    }

    # A blocked or keep-separate formal component retains the source Level 2 ID.
    for context in row_context.values():
        accepted = context["activation_status"] in ACCEPTED_STATUSES
        context["effective_level2"] = (
            context["deterministic_level2"]
            if accepted
            else context["normalized_relation"]
        )
        context["effective_direction"] = (
            context["direction_to_level2"] if accepted else "same"
        )

    # Level 1 is assigned only when an existing catalog family is unambiguous
    # across all source rows in the accepted Level 2 group.
    effective_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for context in row_context.values():
        effective_groups[context["effective_level2"]].append(context)

    level1_by_level2: dict[str, dict[str, str]] = {}
    for level2, members in effective_groups.items():
        existing_families = {
            member["old_level1_family"]
            for member in members
            if member["old_level1_status"] == "EXISTING_CATALOG_ASSIGNMENT"
            and member["old_level1_family"] != "UNRESOLVED"
        }
        candidates = {
            member["old_level1_candidate"]
            for member in members
            if member["old_level1_candidate"]
            and member["old_level1_candidate"] != "UNRESOLVED"
        }
        if len(existing_families) == 1:
            family = next(iter(existing_families))
            status = "EXISTING_CATALOG_ASSIGNMENT"
            source = "RELATION_MAPPING_TABLE_v1.0.0 existing catalog family"
        else:
            family = "UNRESOLVED"
            status = "RANKED_REVIEW_REQUIRED"
            source = ""
        level1_by_level2[level2] = {
            "family": family,
            "status": status,
            "source": source,
            "candidates": joined(candidates),
        }

    connection_ids: dict[tuple[str, str, str], str] = {
        key: connection_id(key) for key in grouped_connections
    }
    connection_keys_by_source: dict[tuple[str, str], set[tuple[str, str, str]]] = (
        defaultdict(set)
    )
    for key, members in grouped_connections.items():
        for member in members:
            connection_keys_by_source[
                (member["left_source"], member["left_relation"])
            ].add(key)
            connection_keys_by_source[
                (member["right_source"], member["right_relation"])
            ].add(key)

    connection_rows: list[dict[str, object]] = []
    for key, members in sorted(grouped_connections.items()):
        left_relation, right_relation, direction = key
        representative = members[0]
        assert len({row["activation_status"] for row in members}) == 1
        assert len({row["canonical_level2"] for row in members}) == 1
        left_keys = {(row["left_source"], row["left_relation"]) for row in members}
        right_keys = {(row["right_source"], row["right_relation"]) for row in members}
        left_occurrences = sum(
            int(registry_by_key[item]["occurrence_count"]) for item in left_keys
        )
        right_occurrences = sum(
            int(registry_by_key[item]["occurrence_count"]) for item in right_keys
        )
        same_code = left_relation == right_relation
        decision = connection_decision(representative)
        accepted_cross = decision.startswith("ACCEPT_FORMAL_TRANSLATION")
        if same_code:
            result = left_relation
        elif accepted_cross:
            result = representative["canonical_level2"]
        else:
            result = "KEEP_SEPARATE"

        if same_code and left_relation in symmetric_relations:
            reverse_policy = "ALLOW_SAME_RELATION_REVERSE_SYMMETRIC"
        elif direction == "reverse" and accepted_cross:
            reverse_policy = "QUERY_REWRITE_USING_FORMAL_INVERSE"
        else:
            reverse_policy = "INBOUND_TRAVERSAL_ONLY"

        left_level1 = level1_by_level2.get(left_relation, {})
        right_level1 = level1_by_level2.get(right_relation, {})
        result_level1 = level1_by_level2.get(result, {})
        same_review = same_validation.get(left_relation, {}) if same_code else {}
        connection_rows.append(
            {
                "connection_v2_id": connection_ids[key],
                "left_relation": left_relation,
                "left_labels": joined({row["left_label"] for row in members}),
                "left_sources": joined({row["left_source"] for row in members}),
                "left_source_relation_rows": len(left_keys),
                "left_source_occurrences": left_occurrences,
                "right_relation": right_relation,
                "right_labels": joined({row["right_label"] for row in members}),
                "right_sources": joined({row["right_source"] for row in members}),
                "right_source_relation_rows": len(right_keys),
                "right_source_occurrences": right_occurrences,
                "connection_class": (
                    "SAME_NORMALIZED_CODE"
                    if same_code
                    else (
                        "FORMAL_INVERSE_PATH"
                        if direction == "reverse"
                        else "FORMAL_EQUIVALENCE_PATH"
                    )
                ),
                "source_logic": (
                    "The normalized Wikidata property ID is equal on both source rows."
                    if same_code
                    else "An explicit formal equivalence or inverse path connects the identifiers."
                ),
                "formal_mapping_sources": (
                    "SOURCE_IDENTIFIERS"
                    if same_code
                    else joined({row["evidence_sources"] for row in members})
                ),
                "formal_paths": (
                    f"{left_relation} IDENTICAL {right_relation}"
                    if same_code
                    else joined({row["formal_path"] for row in members})
                ),
                "evidence_urls": joined({row["evidence_urls"] for row in members}),
                "direction_left_to_right": direction,
                "proposed_canonical_level2": representative["canonical_level2"],
                "mapping_decision": decision,
                "accepted_level2_result": result,
                "formal_component_conflict": representative[
                    "formal_component_conflict"
                ],
                "name_description_review": joined(
                    {row["name_description_review"] for row in members}
                ),
                "example_review": (
                    same_review.get("sample_semantic_review", "")
                    if same_code
                    else joined({row["example_review"] for row in members})
                ),
                "left_level1_family": left_level1.get("family", "UNRESOLVED"),
                "right_level1_family": right_level1.get("family", "UNRESOLVED"),
                "accepted_result_level1_family": result_level1.get(
                    "family", "UNRESOLVED"
                ),
                "level1_use": "OPTIONAL_SEARCH_VIEW_ONLY",
                "reverse_query_policy": reverse_policy,
                "materialize_reverse_edge": "NO",
                "relation_map_version": "relation-map-v2.0.0",
            }
        )

    mapping_rows: list[dict[str, object]] = []
    coverage_counts: Counter[str] = Counter()
    coverage_occurrences: Counter[str] = Counter()
    for key, context in sorted(row_context.items()):
        related_keys = connection_keys_by_source.get(key, set())
        same_keys = {item for item in related_keys if item[0] == item[1]}
        formal_keys = related_keys - same_keys
        if same_keys and formal_keys:
            coverage = "SAME_CODE_AND_FORMAL_CONNECTION"
        elif same_keys:
            coverage = "SAME_CODE_CONNECTION_ONLY"
        elif formal_keys:
            coverage = "FORMAL_CONNECTION_ONLY"
        elif context["mapping_basis"] == "FORMAL_EQUIVALENCE_OR_INVERSE":
            coverage = "FORMAL_EXTERNAL_TARGET_ONLY"
        else:
            coverage = "NO_CONNECTION_RETAIN_SOURCE_ID"

        occurrence_count = int(context["occurrence_count"])
        coverage_counts[coverage] += 1
        coverage_occurrences[coverage] += occurrence_count

        if context["activation_status"] == "READY_DETERMINISTIC_TRANSLATION":
            decision = (
                "ACCEPT_FORMAL_TRANSLATION"
                if context["mapping_basis"] == "FORMAL_EQUIVALENCE_OR_INVERSE"
                else "RETAIN_OR_SHARE_IDENTICAL_IDENTIFIER"
            )
        elif context["activation_status"] == "TRANSLATION_VALID_ASSERTION_QA_REQUIRED":
            decision = "ACCEPT_FORMAL_TRANSLATION_ASSERTION_QA_REQUIRED"
        elif context["activation_status"] == "KEEP_SEPARATE_OPTIONAL_BROADER_VIEW":
            decision = "KEEP_SEPARATE_OPTIONAL_LEVEL1_SEARCH_VIEW"
        else:
            decision = "RETAIN_SOURCE_ID_BLOCK_FORMAL_TRANSLATION"

        inverse_relations = set()
        for item in formal_keys:
            if item[2] == "reverse":
                inverse_relations.add(item[1] if item[0] == key[1] else item[0])
        if coverage == "FORMAL_EXTERNAL_TARGET_ONLY":
            inverse_relations.update(
                row["right_relation"]
                for row in formal_evidence
                if row["left_relation"] == context["normalized_relation"]
                and row["formal_relation"] == "INVERSE"
            )

        if context["normalized_relation"] in symmetric_relations:
            reverse_policy = "ALLOW_SAME_RELATION_REVERSE_SYMMETRIC"
        elif context["effective_direction"] == "reverse":
            reverse_policy = "QUERY_REWRITE_TO_LEVEL2_AND_SWAP_ENDPOINTS"
        elif inverse_relations:
            reverse_policy = "FORMAL_INVERSE_AVAILABLE_FOR_QUERY_REWRITE"
        else:
            reverse_policy = "INBOUND_TRAVERSAL_ONLY"

        level1 = level1_by_level2[context["effective_level2"]]
        related_members = [
            member
            for item in related_keys
            for member in grouped_connections[item]
            if (member["left_source"], member["left_relation"]) == key
            or (member["right_source"], member["right_relation"]) == key
        ]
        external_evidence = (
            [
                row
                for row in formal_evidence
                if row["left_relation"] == context["normalized_relation"]
                and row["right_relation"] == context["effective_level2"]
                and row["formal_relation"] in {"EQUIVALENT", "INVERSE"}
            ]
            if coverage == "FORMAL_EXTERNAL_TARGET_ONLY"
            else []
        )
        mapping_sources = {member["evidence_sources"] for member in related_members}
        formal_paths = {member["formal_path"] for member in related_members}
        evidence_urls = {member["evidence_urls"] for member in related_members}
        if same_keys:
            mapping_sources.add("SOURCE_IDENTIFIERS")
            formal_paths.add(
                f"{context['normalized_relation']} IDENTICAL {context['normalized_relation']}"
            )
        for evidence in external_evidence:
            mapping_sources.add(evidence["evidence_source"])
            formal_paths.add(
                f"{evidence['left_relation']} {evidence['formal_relation']} {evidence['right_relation']}"
            )
            evidence_urls.add(evidence["evidence_url"])
        mapping_rows.append(
            {
                "source": context["source"],
                "source_predicate": context["source_predicate_uri"],
                "source_predicate_local": context["source_predicate"],
                "source_occurrence_count": occurrence_count,
                "normalized_relation_id": context["normalized_relation"],
                "relation_label": context["label"],
                "relation_description": context["description"],
                "connection_coverage": coverage,
                "connection_count": len(related_keys),
                "connection_v2_ids": joined(
                    {connection_ids[item] for item in related_keys}
                ),
                "same_code_connection_count": len(same_keys),
                "formal_connection_count": len(formal_keys),
                "formal_mapping_sources": joined(mapping_sources),
                "formal_paths": joined(formal_paths),
                "formal_evidence_urls": joined(evidence_urls),
                "level2_relation_id": context["effective_level2"],
                "direction_to_level2": context["effective_direction"],
                "level2_mapping_basis": context["mapping_basis"],
                "level2_decision": decision,
                "formal_component_conflict": context["formal_component_conflict"],
                "assertion_qa_required": (
                    "YES"
                    if context["activation_status"]
                    == "TRANSLATION_VALID_ASSERTION_QA_REQUIRED"
                    else "NO"
                ),
                "level1_family": level1["family"],
                "level1_assignment_status": level1["status"],
                "level1_assignment_source": level1["source"],
                "level1_candidates": level1["candidates"],
                "level1_use": "OPTIONAL_SEARCH_VIEW_ONLY",
                "formal_inverse_relation_ids": joined(inverse_relations),
                "reverse_query_policy": reverse_policy,
                "materialize_reverse_edge": "NO",
                "time_from_input": context["time_from_input"],
                "time_to_input": context["time_to_input"],
                "time_point_input": context["time_point_input"],
                "time_join_rule": context["time_join_rule"],
                "evidence_requirements": context["evidence_requirements"],
                "evidence_policy": context["evidence_policy"],
                "time_conflict_policy": context["time_conflict_policy"],
                "source_data_modified": "False",
                "relation_map_version": "relation-map-v2.0.0",
            }
        )

    assert len(mapping_rows) == 1520
    assert len(connection_rows) == 589
    assert sum(coverage_counts.values()) == 1520
    assert sum(coverage_occurrences.values()) == sum(
        int(row["occurrence_count"]) for row in registry
    )

    coverage_rows = [
        {
            "connection_coverage": coverage,
            "source_relation_rows": coverage_counts[coverage],
            "source_occurrences": coverage_occurrences[coverage],
        }
        for coverage in sorted(coverage_counts)
    ]

    mapping_path = OUT / "RELATION_MAPPING_TABLE_v2.0.0.csv"
    connection_path = OUT / "RELATION_CONNECTIONS_v2.0.0.csv"
    coverage_path = OUT / "RELATION_MAPPING_COVERAGE_v2.0.0.csv"
    write_csv(mapping_path, mapping_rows)
    write_csv(connection_path, connection_rows)
    write_csv(coverage_path, coverage_rows)

    cross_rows = [
        row
        for row in connection_rows
        if row["connection_class"] != "SAME_NORMALIZED_CODE"
    ]
    unconnected = [
        row
        for row in mapping_rows
        if row["connection_coverage"]
        in {"NO_CONNECTION_RETAIN_SOURCE_ID", "FORMAL_EXTERNAL_TARGET_ONLY"}
    ]
    summary = {
        "relation_map_version": "relation-map-v2.0.0",
        "eligible_source_relation_rows": len(mapping_rows),
        "source_occurrences": sum(
            int(row["source_occurrence_count"]) for row in mapping_rows
        ),
        "unique_connection_rows": len(connection_rows),
        "same_code_connections": sum(
            row["connection_class"] == "SAME_NORMALIZED_CODE" for row in connection_rows
        ),
        "cross_identifier_connections": len(cross_rows),
        "cross_identifier_directions": dict(
            Counter(row["direction_left_to_right"] for row in cross_rows)
        ),
        "cross_identifier_decisions": dict(
            Counter(row["mapping_decision"] for row in cross_rows)
        ),
        "source_relation_coverage": {
            row["connection_coverage"]: {
                "source_relation_rows": row["source_relation_rows"],
                "source_occurrences": row["source_occurrences"],
            }
            for row in coverage_rows
        },
        "unconnected_source_relation_rows": len(unconnected),
        "unconnected_source_occurrences": sum(
            int(row["source_occurrence_count"]) for row in unconnected
        ),
        "effective_level2_relations": len(effective_groups),
        "level1_effective_relation_status": dict(
            Counter(item["status"] for item in level1_by_level2.values())
        ),
        "accepted_reverse_source_rows": sum(
            row["direction_to_level2"] == "reverse" for row in mapping_rows
        ),
        "symmetric_level2_relations": len(symmetric_relations),
        "opposite_direction_policy": (
            "Store one source assertion. Use formal inverse or symmetry for query rewriting; otherwise use inbound traversal."
        ),
        "level1_policy": (
            "Optional search view only. Ranked candidates remain unresolved until reviewed."
        ),
        "source_data_modified": False,
    }
    (OUT / "RELATION_MAPPING_V2_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

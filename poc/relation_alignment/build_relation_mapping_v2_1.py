"""Build relation-map v2.1 with data-layer reverse relation outputs.

The Agent must not interpret inverse formulas.  This builder assigns every
effective Level 2 relation one explicit reverse ID and label.  A formal named
inverse is used only when the validated formal graph is unique and involutive.
All other relations receive a deterministic synthetic inverse.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MAPPING_V2 = ROOT / "GG_Data" / "mapping" / "RELATION_MAPPING_TABLE_v2.0.0.csv"
INVENTORY = HERE / "relation_catalog_eda" / "source_predicate_inventory.csv"
REVERSE_VALIDATION = (
    HERE / "reverse_formula_validation" / "reverse_contract_validation.csv"
)
OUT = ROOT / "GG_Data" / "mapping"
VERSION = "relation-map-v2.1.0"
LOOKUP_NAME = "RELATION_DIRECTION_LOOKUP_v2.1.0.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def split_values(value: str) -> list[str]:
    return [item for item in value.split("|") if item]


def pair_id(left: str, right: str) -> str:
    value = "|".join(sorted((left, right)))
    return "direction-pair-" + hashlib.sha256(value.encode()).hexdigest()[:12]


def local_label(relation_id: str) -> str:
    """Return a readable URI local name; opaque property codes stay unlabeled."""
    if relation_id.startswith("wd:P"):
        return ""
    local = unquote(re.split(r"[/#]", relation_id.rstrip("/#"))[-1])
    local = re.sub(r"^P\d+i?_?", "", local)
    local = re.sub(r"[_-]+", " ", local)
    local = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", local)
    return " ".join(local.split()).strip().lower()


def build() -> dict[str, Any]:
    mapping = read_csv(MAPPING_V2)
    contracts = read_csv(REVERSE_VALIDATION)
    inventory = read_csv(INVENTORY)

    contract_by_relation = {row["relation"]: row for row in contracts}
    assert len(contract_by_relation) == len(contracts)

    labels: dict[str, Counter[str]] = defaultdict(Counter)
    for row in mapping:
        if row["relation_label"]:
            weight = max(int(row["source_occurrence_count"]), 1)
            labels[row["normalized_relation_id"]][row["relation_label"]] += weight
    for row in inventory:
        if row["label"]:
            labels[row["source_predicate"]][row["label"]] += max(
                int(row["occurrence_count"]), 1
            )
    for row in contracts:
        for label in split_values(row["labels"]):
            labels[row["relation"]][label] += max(
                int(row["catalog_occurrence_count"]), 1
            )

    def known_label(relation_id: str) -> str:
        if labels[relation_id]:
            return sorted(
                labels[relation_id],
                key=lambda value: (-labels[relation_id][value], value),
            )[0]
        return local_label(relation_id)

    members: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mapping:
        members[row["level2_relation_id"]].append(row)

    direction_catalog: list[dict[str, Any]] = []
    for relation_id, source_rows in sorted(members.items()):
        forward_label = known_label(relation_id) or relation_id
        contract = contract_by_relation.get(relation_id)
        candidates = split_values(contract["reverse_candidates"]) if contract else []
        prior_policies = sorted({row["reverse_query_policy"] for row in source_rows})
        prior_named_ids = sorted(
            {
                value
                for row in source_rows
                for value in split_values(row["formal_inverse_relation_ids"])
            }
        )
        prior_v2_handled = bool(
            set(prior_policies)
            & {
                "FORMAL_INVERSE_AVAILABLE_FOR_QUERY_REWRITE",
                "QUERY_REWRITE_TO_LEVEL2_AND_SWAP_ENDPOINTS",
                "ALLOW_SAME_RELATION_REVERSE_SYMMETRIC",
            }
        )

        if contract and contract["formula_status"] == "PASS_SYMMETRIC_SELF_REVERSE":
            reverse_id = relation_id
            reverse_label = forward_label
            resolution_type = "SYMMETRIC"
            status = "ACTIVE_FORMAL_SYMMETRIC"
            label_source = "SAME_AS_LEVEL2_LABEL"
            change = (
                "PRESERVE_FORMAL_REVERSE"
                if prior_v2_handled
                else "ACTIVATE_FORMAL_REVERSE"
            )
        elif contract and contract["formula_status"] == "PASS_NAMED_INVERSE":
            assert len(candidates) == 1
            reverse_id = candidates[0]
            reverse_label = known_label(reverse_id)
            label_source = "RELATION_CATALOG"
            if not reverse_label:
                reverse_label = f"inverse of {forward_label}"
                label_source = "DERIVED_FROM_LEVEL2_LABEL"
            resolution_type = "NAMED_INVERSE"
            status = "ACTIVE_FORMAL_NAMED_INVERSE"
            change = (
                "PRESERVE_FORMAL_REVERSE"
                if prior_v2_handled
                else "ACTIVATE_FORMAL_REVERSE"
            )
        else:
            reverse_id = f"inverse:{relation_id}"
            reverse_label = f"inverse of {forward_label}"
            resolution_type = "SYNTHETIC_INVERSE"
            label_source = "DERIVED_FROM_LEVEL2_LABEL"
            status = (
                "ACTIVE_SYNTHETIC_AMBIGUOUS_NAMED_INVERSE"
                if contract
                else "ACTIVE_SYNTHETIC_NO_FORMAL_NAMED_INVERSE"
            )
            change = (
                "BLOCK_AMBIGUOUS_NAMED_AND_ADD_SYNTHETIC"
                if contract
                else "ADD_SYNTHETIC_REVERSE"
            )

        formal_sources = split_values(contract["formal_sources"]) if contract else []
        formal_bases = split_values(contract["formal_bases"]) if contract else []
        evidence_urls = split_values(contract["evidence_urls"]) if contract else []
        direction_catalog.append(
            {
                "direction_pair_id": pair_id(relation_id, reverse_id),
                "level2_relation_id": relation_id,
                "level2_relation_label": forward_label,
                "reverse_relation_id": reverse_id,
                "reverse_relation_label": reverse_label,
                "reverse_resolution_type": resolution_type,
                "reverse_status": status,
                "reverse_label_source": label_source,
                "v2_1_change": change,
                "prior_v2_reverse_policy": "|".join(prior_policies),
                "prior_v2_named_reverse_ids": "|".join(prior_named_ids),
                "formal_reverse_candidate_ids": "|".join(candidates),
                "formal_reverse_candidate_count": len(candidates),
                "formal_sources": "|".join(formal_sources),
                "formal_bases": "|".join(formal_bases),
                "formal_evidence_urls": "|".join(evidence_urls),
                "endpoint_action": "SWAP_SOURCE_TARGET",
                "reverse_of_reverse_relation_id": relation_id,
                "data_layer_delivery": "QUERY_OR_EXPORT_DIRECTIONAL_VIEW",
                "agent_action_required": "NONE",
                "source_relation_rows": len(source_rows),
                "source_occurrences": sum(
                    int(row["source_occurrence_count"]) for row in source_rows
                ),
                "relation_map_version": VERSION,
            }
        )

    direction_by_level2 = {row["level2_relation_id"]: row for row in direction_catalog}
    assert len(direction_by_level2) == len(direction_catalog) == 1009
    direction_pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in direction_catalog:
        direction_pairs[row["direction_pair_id"]].append(row)
    assert all(1 <= len(rows) <= 2 for rows in direction_pairs.values())
    for rows in direction_pairs.values():
        if len(rows) == 2:
            left, right = rows
            assert left["reverse_relation_id"] == right["level2_relation_id"]
            assert right["reverse_relation_id"] == left["level2_relation_id"]

    lookup_by_relation: dict[str, dict[str, Any]] = {}
    for direction in direction_catalog:
        forward_id = direction["level2_relation_id"]
        reverse_id = direction["reverse_relation_id"]
        entries = [
            (
                forward_id,
                direction["level2_relation_label"],
                reverse_id,
                direction["reverse_relation_label"],
                "SYMMETRIC" if forward_id == reverse_id else "FORWARD_TO_REVERSE",
                True,
            )
        ]
        if forward_id != reverse_id:
            entries.append(
                (
                    reverse_id,
                    direction["reverse_relation_label"],
                    forward_id,
                    direction["level2_relation_label"],
                    "REVERSE_TO_FORWARD",
                    reverse_id in direction_by_level2,
                )
            )

        for (
            input_id,
            input_label,
            output_id,
            output_label,
            lookup_side,
            input_is_level2,
        ) in entries:
            lookup = {
                "direction_pair_id": direction["direction_pair_id"],
                "input_relation_id": input_id,
                "input_relation_label": input_label,
                "output_reverse_relation_id": output_id,
                "output_reverse_relation_label": output_label,
                "lookup_side": lookup_side,
                "input_is_effective_level2_relation": str(input_is_level2).lower(),
                "reverse_resolution_type": direction["reverse_resolution_type"],
                "is_symmetric": str(forward_id == reverse_id).lower(),
                "endpoint_action": "SWAP_SOURCE_TARGET",
                "formal_sources": direction["formal_sources"],
                "formal_bases": direction["formal_bases"],
                "formal_evidence_urls": direction["formal_evidence_urls"],
                "agent_action_required": "NONE",
                "relation_map_version": VERSION,
            }
            existing = lookup_by_relation.get(input_id)
            if existing:
                assert existing["output_reverse_relation_id"] == output_id
                assert existing["output_reverse_relation_label"] == output_label
                assert existing["direction_pair_id"] == direction["direction_pair_id"]
                continue
            lookup_by_relation[input_id] = lookup

    direction_lookup = [lookup_by_relation[key] for key in sorted(lookup_by_relation)]
    assert len(direction_lookup) == 1995
    assert sum(row["lookup_side"] == "SYMMETRIC" for row in direction_lookup) == 9
    assert all(row["agent_action_required"] == "NONE" for row in direction_lookup)
    for row in direction_lookup:
        reverse = lookup_by_relation[row["output_reverse_relation_id"]]
        assert reverse["output_reverse_relation_id"] == row["input_relation_id"]
        assert reverse["direction_pair_id"] == row["direction_pair_id"]

    mapping_v2_1: list[dict[str, Any]] = []
    for row in mapping:
        direction = direction_by_level2[row["level2_relation_id"]]
        updated = dict(row)
        updated.update(
            {
                "level2_relation_label": direction["level2_relation_label"],
                "direction_pair_id": direction["direction_pair_id"],
                "reverse_relation_id": direction["reverse_relation_id"],
                "reverse_relation_label": direction["reverse_relation_label"],
                "reverse_resolution_type": direction["reverse_resolution_type"],
                "reverse_status": direction["reverse_status"],
                "reverse_label_source": direction["reverse_label_source"],
                "reverse_v2_1_change": direction["v2_1_change"],
                "prior_v2_reverse_policy": direction["prior_v2_reverse_policy"],
                "prior_v2_named_reverse_ids": direction["prior_v2_named_reverse_ids"],
                "level2_formal_reverse_candidate_ids": direction[
                    "formal_reverse_candidate_ids"
                ],
                "level2_formal_reverse_candidate_count": direction[
                    "formal_reverse_candidate_count"
                ],
                "reverse_formal_sources": direction["formal_sources"],
                "reverse_formal_bases": direction["formal_bases"],
                "reverse_evidence_urls": direction["formal_evidence_urls"],
                "reverse_endpoint_action": direction["endpoint_action"],
                "reverse_of_reverse_relation_id": direction[
                    "reverse_of_reverse_relation_id"
                ],
                "reverse_data_layer_delivery": direction["data_layer_delivery"],
                "reverse_agent_action_required": direction["agent_action_required"],
                "reverse_query_policy": {
                    "SYMMETRIC": "DATA_LAYER_RETURN_SAME_RELATION_AND_SWAP_ENDPOINTS",
                    "NAMED_INVERSE": "DATA_LAYER_RETURN_NAMED_INVERSE_AND_SWAP_ENDPOINTS",
                    "SYNTHETIC_INVERSE": "DATA_LAYER_RETURN_SYNTHETIC_INVERSE_AND_SWAP_ENDPOINTS",
                }[direction["reverse_resolution_type"]],
                "relation_map_version": VERSION,
            }
        )
        mapping_v2_1.append(updated)

    assert len(mapping_v2_1) == len(mapping) == 1520
    assert all(row["reverse_relation_id"] for row in mapping_v2_1)
    assert all(row["reverse_relation_label"] for row in mapping_v2_1)
    assert all(row["reverse_agent_action_required"] == "NONE" for row in mapping_v2_1)
    assert all(
        row["reverse_of_reverse_relation_id"] == row["level2_relation_id"]
        for row in mapping_v2_1
    )
    assert all(
        row["reverse_relation_id"] == row["level2_relation_id"]
        for row in mapping_v2_1
        if row["reverse_resolution_type"] == "SYMMETRIC"
    )
    assert all(
        row["reverse_relation_id"].startswith("inverse:")
        for row in mapping_v2_1
        if row["reverse_resolution_type"] == "SYNTHETIC_INVERSE"
    )
    assert all(
        not row["reverse_relation_id"].startswith("inverse:")
        for row in mapping_v2_1
        if row["reverse_resolution_type"] == "NAMED_INVERSE"
    )

    write_csv(OUT / "RELATION_DIRECTION_CATALOG_v2.1.0.csv", direction_catalog)
    write_csv(OUT / LOOKUP_NAME, direction_lookup)
    write_csv(OUT / "RELATION_MAPPING_TABLE_v2.1.0.csv", mapping_v2_1)

    type_counts = Counter(row["reverse_resolution_type"] for row in direction_catalog)
    status_counts = Counter(row["reverse_status"] for row in direction_catalog)
    occurrence_counts = Counter()
    for row in direction_catalog:
        occurrence_counts[row["reverse_resolution_type"]] += int(
            row["source_occurrences"]
        )
    summary = {
        "relation_map_version": VERSION,
        "source_mapping_rows": len(mapping_v2_1),
        "source_occurrences": sum(
            int(row["source_occurrence_count"]) for row in mapping_v2_1
        ),
        "effective_level2_relations": len(direction_catalog),
        "unique_direction_pairs": len(direction_pairs),
        "direction_lookup_rows": len(direction_lookup),
        "direction_lookup_non_symmetric_rows": sum(
            row["lookup_side"] != "SYMMETRIC" for row in direction_lookup
        ),
        "direction_lookup_symmetric_rows": sum(
            row["lookup_side"] == "SYMMETRIC" for row in direction_lookup
        ),
        "reverse_resolution_types": dict(type_counts),
        "reverse_statuses": dict(status_counts),
        "source_occurrences_by_reverse_resolution_type": dict(occurrence_counts),
        "relations_with_explicit_reverse_id": sum(
            bool(row["reverse_relation_id"]) for row in direction_catalog
        ),
        "relations_with_explicit_reverse_label": sum(
            bool(row["reverse_relation_label"]) for row in direction_catalog
        ),
        "formal_safe_relations_activated": sum(
            row["reverse_resolution_type"] in {"NAMED_INVERSE", "SYMMETRIC"}
            for row in direction_catalog
        ),
        "previous_v2_formal_reverse_relations_preserved": sum(
            row["v2_1_change"] == "PRESERVE_FORMAL_REVERSE" for row in direction_catalog
        ),
        "previous_v2_missing_formal_reverse_relations_activated": sum(
            row["v2_1_change"] == "ACTIVATE_FORMAL_REVERSE" for row in direction_catalog
        ),
        "formal_ambiguous_relations_using_synthetic_inverse": sum(
            row["reverse_status"] == "ACTIVE_SYNTHETIC_AMBIGUOUS_NAMED_INVERSE"
            for row in direction_catalog
        ),
        "agent_reverse_interpretation_required": False,
        "endpoint_action": "SWAP_SOURCE_TARGET",
        "delivery_policy": (
            "The data layer returns a resolved directional assertion. The Agent "
            "receives the reversed subject, explicit relation ID and label, and "
            "reversed object."
        ),
        "inputs": {
            "mapping_v2": str(MAPPING_V2.relative_to(ROOT)),
            "reverse_validation": str(REVERSE_VALIDATION.relative_to(ROOT)),
            "source_inventory": str(INVENTORY.relative_to(ROOT)),
        },
    }
    (OUT / "RELATION_MAPPING_V2_1_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

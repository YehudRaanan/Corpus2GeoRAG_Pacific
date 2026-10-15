"""Create a reproducible sanity sample for relation-map v2.1.0.

The check replays the v2.1 mapping over the assertions used by the current
WWII Agent draft.  It does not change source data and it does not call a model.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


DEFAULT_SEED = 20_261_015
DEFAULT_SAMPLE_SIZE = 5

QUESTION_RELATIONS = {
    "where_event": {"wd:P276", "wd:P131", "wd:P706"},
    "participation_or_command": {
        "wd:P607",
        "wd:P1344",
        "wd:P710",
        "wd:P598",
        "wd:P4791",
        "http://dbpedia.org/ontology/commander",
        "http://yago-knowledge.org/resource/participatedIn",
    },
    "part_whole": {"wd:P361", "wd:P527"},
    "organization_place": {
        "wd:P159",
        "wd:P466",
        "http://dbpedia.org/ontology/garrison",
    },
    "person_place": {"wd:P19", "wd:P20", "wd:P119", "wd:P551", "wd:P937", "wd:P2632"},
}

QUESTION_USE_LIMITS = {
    "wd:P276": "Location candidate only; verify event subject, place target, and place scale.",
    "wd:P131": "Administrative containment; not sufficient proof that an event occurred there.",
    "wd:P706": "Physical-feature location; not sufficient proof that an event occurred there.",
    "wd:P607": "Conflict affiliation; supports conflict participation, not attacker or defender role.",
    "wd:P1344": "Participation in an event; does not identify attacker, defender, or commander role.",
    "wd:P710": "Event participant; does not identify attacker, defender, or commander role.",
    "wd:P598": "Commander-of relation; verify that the commanded object is the entity asked about.",
    "wd:P4791": "Commanded-by relation; verify that the subject is the entity asked about.",
    "http://dbpedia.org/ontology/commander": "Commander relation; verify endpoint roles before use.",
    "http://yago-knowledge.org/resource/participatedIn": "Participation only; does not prove attack.",
    "wd:P361": "Part-of hierarchy; useful for expansion, not direct event or action evidence.",
    "wd:P527": "Has-part hierarchy; useful for expansion, not direct event or action evidence.",
    "wd:P159": "Headquarters location; does not prove an attack, occupation, or event location.",
    "wd:P466": "Occupant relation; does not prove an attack or headquarters relation.",
    "http://dbpedia.org/ontology/garrison": "Garrison relation; verify endpoint roles and source meaning.",
    "wd:P19": "Birth place only.",
    "wd:P20": "Death place only.",
    "wd:P119": "Burial place only.",
    "wd:P551": "Residence only.",
    "wd:P937": "Work location only.",
    "wd:P2632": "Place of detention only.",
}


@dataclass
class Reservoir:
    limit: int
    rng: random.Random
    seen: int = 0
    rows: list[dict[str, str]] | None = None

    def __post_init__(self) -> None:
        self.rows = []

    def add(self, row: dict[str, str]) -> None:
        self.seen += 1
        assert self.rows is not None
        if len(self.rows) < self.limit:
            self.rows.append(row)
            return
        index = self.rng.randrange(self.seen)
        if index < self.limit:
            self.rows[index] = row


def iter_json_array(path: Path, key: str) -> Iterator[dict[str, Any]]:
    """Stream objects from one top-level JSON array with the standard library."""
    marker = f'"{key}":['
    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as stream:
        buffer = ""
        while marker not in buffer:
            chunk = stream.read(1 << 20)
            if not chunk:
                raise ValueError(f"Array {key!r} was not found in {path}")
            buffer += chunk
            position = buffer.find(marker)
            if position < 0:
                buffer = buffer[-len(marker) :]
        buffer = buffer[buffer.find(marker) + len(marker) :]

        while True:
            buffer = buffer.lstrip()
            if buffer.startswith("]"):
                return
            if buffer.startswith(","):
                buffer = buffer[1:].lstrip()
            while True:
                try:
                    item, end = decoder.raw_decode(buffer)
                    break
                except json.JSONDecodeError:
                    chunk = stream.read(1 << 20)
                    if not chunk:
                        raise
                    buffer += chunk
            if not isinstance(item, dict):
                raise TypeError(f"Expected an object in {key!r}, got {type(item).__name__}")
            yield item
            buffer = buffer[end:]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def risk_stratum(mapping: dict[str, str]) -> str:
    decision = mapping["level2_decision"]
    if mapping["assertion_qa_required"] == "YES":
        return "ASSERTION_QA_REQUIRED"
    if "BLOCK" in decision or "KEEP_SEPARATE" in decision:
        return "BLOCKED_OR_KEPT_SEPARATE"
    if mapping["level2_mapping_basis"] == "FORMAL_EQUIVALENCE_OR_INVERSE":
        return "FORMAL_REVERSE" if mapping["direction_to_level2"] == "reverse" else "FORMAL_SAME"
    if mapping["connection_coverage"] == "NO_CONNECTION_RETAIN_SOURCE_ID":
        return "RETAINED_UNCONNECTED"
    return "IDENTICAL_CONNECTED"


def question_groups(relation_id: str) -> list[str]:
    return [name for name, relations in QUESTION_RELATIONS.items() if relation_id in relations]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "sanity_check_v2_1",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    mapping_path = root / "GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv"
    direction_path = root / "GG_Data/mapping/RELATION_DIRECTION_LOOKUP_v2.1.0.csv"
    assertions_path = (
        root / "GG_Data/mapping/outputs/relation-map-v1.0.0/complete_mapped_relations_v1.0.0.csv"
    )
    graph_path = root / "GG_Data/agent_export/outputs/wwii_agent_graph_draft_v0.1.0.json"
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    mapping_rows = read_csv(mapping_path)
    mapping_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in mapping_rows:
        key = (row["source"], row["source_predicate"])
        mapping_groups[key].append(row)

    duplicate_mapping_keys = {key: rows for key, rows in mapping_groups.items() if len(rows) > 1}
    conflicting_mapping_keys: dict[tuple[str, str], list[dict[str, str]]] = {}
    mapping_lookup: dict[tuple[str, str], dict[str, str]] = {}
    for key, rows in mapping_groups.items():
        signatures = {
            (
                row["level2_relation_id"],
                row["direction_to_level2"],
                row["level2_decision"],
                row["reverse_relation_id"],
            )
            for row in rows
        }
        if len(signatures) > 1:
            conflicting_mapping_keys[key] = rows
        else:
            mapping_lookup[key] = rows[0]

    direction_rows = read_csv(direction_path)
    direction_lookup = {row["input_relation_id"]: row for row in direction_rows}
    direction_errors: list[str] = []
    for row in mapping_rows:
        relation_id = row["level2_relation_id"]
        reverse_id = row["reverse_relation_id"]
        direct = direction_lookup.get(relation_id)
        reverse = direction_lookup.get(reverse_id)
        if direct is None:
            direction_errors.append(f"missing lookup for {relation_id}")
            continue
        if direct["output_reverse_relation_id"] != reverse_id:
            direction_errors.append(f"reverse mismatch for {relation_id}")
        if reverse is None or reverse["output_reverse_relation_id"] != relation_id:
            direction_errors.append(f"reverse-of-reverse mismatch for {relation_id}")

    node_index: dict[str, tuple[str, str]] = {}
    for node in iter_json_array(graph_path, "nodes"):
        node_index[str(node["id"])] = (str(node.get("name", "")), str(node.get("type", "")))

    rng = random.Random(args.seed)
    samples: dict[str, Reservoir] = defaultdict(lambda: Reservoir(args.sample_size, rng))
    counts: Counter[str] = Counter()
    missing_keys: Counter[tuple[str, str, str]] = Counter()
    question_relation_counts: Counter[tuple[str, str]] = Counter()
    question_type_pairs: Counter[tuple[str, str, str, str]] = Counter()

    with assertions_path.open(encoding="utf-8", newline="") as stream:
        for assertion in csv.DictReader(stream):
            counts["assertions_total"] += 1
            key = (assertion["selected_source"], assertion["selected_source_predicate"])
            if key in conflicting_mapping_keys:
                counts["assertions_with_ambiguous_v2_mapping_key"] += 1
                continue
            mapping = mapping_lookup.get(key)
            if mapping is None:
                counts["assertions_without_v2_mapping"] += 1
                missing_key = (key[0], key[1], assertion["level2_relation"])
                missing_keys[missing_key] += 1
                sample = {
                    "sample_group": "risk:MISSING_MAPPING",
                    "observation_id": assertion["observation_id"],
                    "source_dataset": key[0],
                    "source_predicate": key[1],
                    "source_relation_label": "",
                    "level2_relation_id": assertion["level2_relation"],
                    "level2_relation_label": assertion["level2_label"],
                    "direction_to_level2": assertion["direction"],
                    "level2_mapping_basis": "NO_V2_ROW",
                    "level2_decision": "NO_V2_ROW",
                    "level1_family": assertion["level1_relation"],
                    "reverse_relation_id": "",
                    "reverse_resolution_type": "",
                    "original_subject_id": assertion["subject_qid"],
                    "original_object_id": assertion["object_qid"],
                    "canonical_subject_id": assertion["subject_qid"],
                    "canonical_object_id": assertion["object_qid"],
                    "question_use_limit": "A v2.1 assignment does not exist for this source predicate.",
                }
                samples["risk:MISSING_MAPPING"].add(sample)
                continue

            counts["assertions_with_v2_mapping"] += 1
            direction = mapping["direction_to_level2"]
            original_subject = assertion["subject_qid"]
            original_object = assertion["object_qid"]
            canonical_subject, canonical_object = original_subject, original_object
            if direction == "reverse":
                canonical_subject, canonical_object = canonical_object, canonical_subject

            relation_id = mapping["level2_relation_id"]
            base = {
                "observation_id": assertion["observation_id"],
                "source_dataset": key[0],
                "source_predicate": key[1],
                "source_relation_label": mapping["relation_label"],
                "level2_relation_id": relation_id,
                "level2_relation_label": mapping["level2_relation_label"],
                "direction_to_level2": direction,
                "level2_mapping_basis": mapping["level2_mapping_basis"],
                "level2_decision": mapping["level2_decision"],
                "level1_family": mapping["level1_family"],
                "reverse_relation_id": mapping["reverse_relation_id"],
                "reverse_resolution_type": mapping["reverse_resolution_type"],
                "original_subject_id": original_subject,
                "original_object_id": original_object,
                "canonical_subject_id": canonical_subject,
                "canonical_object_id": canonical_object,
                "question_use_limit": QUESTION_USE_LIMITS.get(relation_id, ""),
            }

            stratum = risk_stratum(mapping)
            counts[f"risk:{stratum}"] += 1
            risk_sample = dict(base, sample_group=f"risk:{stratum}")
            samples[f"risk:{stratum}"].add(risk_sample)

            subject_type = node_index.get(canonical_subject, ("", "MISSING_NODE"))[1]
            object_type = node_index.get(canonical_object, ("", "MISSING_NODE"))[1]
            for group in question_groups(relation_id):
                counts[f"question:{group}"] += 1
                question_relation_counts[(group, relation_id)] += 1
                question_type_pairs[(group, relation_id, subject_type, object_type)] += 1
                sample_key = f"question:{group}:{relation_id}"
                samples[sample_key].add(dict(base, sample_group=sample_key))

    sample_rows: list[dict[str, str]] = []
    for group in sorted(samples):
        reservoir = samples[group]
        assert reservoir.rows is not None
        for row in reservoir.rows:
            for side in ("original_subject", "original_object", "canonical_subject", "canonical_object"):
                qid = row[f"{side}_id"]
                name, node_type = node_index.get(qid, (qid, "MISSING_NODE"))
                row[f"{side}_name"] = name
                row[f"{side}_type"] = node_type
            sample_rows.append(row)

    fieldnames = [
        "sample_group",
        "observation_id",
        "source_dataset",
        "source_predicate",
        "source_relation_label",
        "level2_relation_id",
        "level2_relation_label",
        "direction_to_level2",
        "level2_mapping_basis",
        "level2_decision",
        "level1_family",
        "reverse_relation_id",
        "reverse_resolution_type",
        "original_subject_id",
        "original_subject_name",
        "original_subject_type",
        "original_object_id",
        "original_object_name",
        "original_object_type",
        "canonical_subject_id",
        "canonical_subject_name",
        "canonical_subject_type",
        "canonical_object_id",
        "canonical_object_name",
        "canonical_object_type",
        "question_use_limit",
    ]
    sample_path = output_dir / "relation_mapping_sanity_sample.csv"
    with sample_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sample_rows)

    missing_path = output_dir / "missing_v2_mapping_rows.csv"
    with missing_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["source", "source_predicate", "v1_relation_id", "assertion_count"])
        for key, count in missing_keys.most_common():
            writer.writerow([*key, count])

    ambiguous_path = output_dir / "ambiguous_v2_mapping_keys.csv"
    with ambiguous_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "source",
                "source_predicate",
                "normalized_relation_id",
                "level2_relation_id",
                "direction_to_level2",
                "level2_decision",
                "source_occurrence_count",
            ]
        )
        for key, rows in sorted(conflicting_mapping_keys.items()):
            for row in rows:
                writer.writerow(
                    [
                        *key,
                        row["normalized_relation_id"],
                        row["level2_relation_id"],
                        row["direction_to_level2"],
                        row["level2_decision"],
                        row["source_occurrence_count"],
                    ]
                )

    question_counts_path = output_dir / "question_relation_counts.csv"
    with question_counts_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["question_group", "level2_relation_id", "assertion_count", "question_use_limit"])
        for (group, relation_id), count in sorted(question_relation_counts.items()):
            writer.writerow([group, relation_id, count, QUESTION_USE_LIMITS.get(relation_id, "")])

    type_pairs_path = output_dir / "question_relation_type_pairs.csv"
    with type_pairs_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["question_group", "level2_relation_id", "canonical_subject_type", "canonical_object_type", "assertion_count"]
        )
        for key, count in sorted(question_type_pairs.items()):
            writer.writerow([*key, count])

    total = counts["assertions_total"]
    mapped = counts["assertions_with_v2_mapping"]
    summary = {
        "relation_map_version": "relation-map-v2.1.0",
        "assertion_source_version": "relation-map-v1.0.0",
        "graph_version": "wwii-agent-draft-v0.1.0",
        "seed": args.seed,
        "sample_size_per_stratum": args.sample_size,
        "mapping_rows": len(mapping_rows),
        "duplicate_source_predicate_keys": len(duplicate_mapping_keys),
        "extra_rows_under_duplicate_keys": sum(len(rows) - 1 for rows in duplicate_mapping_keys.values()),
        "conflicting_source_predicate_keys": len(conflicting_mapping_keys),
        "direction_lookup_rows": len(direction_rows),
        "direction_contract_errors": len(set(direction_errors)),
        "direction_contract_error_examples": sorted(set(direction_errors))[:20],
        "graph_nodes_indexed": len(node_index),
        "assertions_total": total,
        "assertions_with_v2_mapping": mapped,
        "assertions_with_v2_mapping_percent": round(100 * mapped / total, 2),
        "assertions_without_v2_mapping": counts["assertions_without_v2_mapping"],
        "assertions_without_v2_mapping_percent": round(
            100 * counts["assertions_without_v2_mapping"] / total, 2
        ),
        "missing_source_predicate_keys": len(missing_keys),
        "assertions_with_ambiguous_v2_mapping_key": counts[
            "assertions_with_ambiguous_v2_mapping_key"
        ],
        "risk_counts": {
            key.removeprefix("risk:"): value
            for key, value in sorted(counts.items())
            if key.startswith("risk:")
        },
        "question_group_counts": {
            key.removeprefix("question:"): value
            for key, value in sorted(counts.items())
            if key.startswith("question:")
        },
        "sample_rows": len(sample_rows),
        "limits": [
            "The published Agent repository describes a 56-question Gold Set, but does not publish gold.jsonl.",
            "The check uses the documented question patterns and relation roles, not the unavailable expected answers.",
            "The assertion file and graph were built with relation-map v1.0.0; v2.1 is replayed in this check.",
            "Node types and names come from the draft graph and can themselves be wrong or unresolved.",
            "Random samples find obvious problems but do not prove that all assertions are correct.",
        ],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

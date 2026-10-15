"""Retain up to ten reproducible distinct facts per added source key.

No model is called. Labels are presentation aids from the existing draft,
not identity gold. Missing counterpart assertions do not contradict a rule.
"""

from __future__ import annotations

import csv
import hashlib
import heapq
import json
from collections import Counter, defaultdict
from pathlib import Path

from rebuild_relation_mapping import normalize_uri, read_csv, write_csv
from run_relation_mapping_sanity import iter_json_array, original_endpoints


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RULES = OUT / "ADDITIONAL_RELATION_RULES_2026-10-15.csv"


def main() -> None:
    rules = read_csv(RULES)
    by_key = {(row["source"], row["source_predicate"]): row for row in rules}
    assert len(by_key) == len(rules) == 75
    snapshots = json.loads(
        (OUT / rules[0]["metadata_snapshot"]).read_text(encoding="utf-8")
    )
    inverse_ids: dict[str, set[str]] = defaultdict(set)
    for pid, entity in snapshots["entities"].items():
        for statement in entity["claims"].get("P1696", []):
            if statement.get("rank") == "deprecated" or statement.get("qualifiers"):
                continue
            target = (
                statement["mainsnak"].get("datavalue", {}).get("value", {}).get("id")
            )
            if target:
                inverse_ids[f"wd:{pid}"].add(f"wd:{target}")
    needed_ids = {row["normalized_relation_id"] for row in rules}
    needed_ids.update(target for values in inverse_ids.values() for target in values)
    facts: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    seen: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str], list[tuple[int, str, dict[str, str]]]] = defaultdict(
        list
    )
    counts: Counter[tuple[str, str]] = Counter()
    assertions = (
        OUT / "outputs/relation-map-v1.0.0/complete_mapped_relations_v1.0.0.csv"
    )
    with assertions.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["selected_source"], row["selected_source_predicate"])
            predicate = normalize_uri(key[1])
            subject, obj = original_endpoints(row)
            if predicate in needed_ids:
                facts[(predicate, subject, obj)].add(key[0])
            if key not in by_key:
                continue
            counts[key] += 1
            fact = (subject, obj)
            if fact in seen[key]:
                continue
            seen[key].add(fact)
            # Lowest ten SHA256 values: stable selection, independent of file order.
            token = "|".join((*key, *fact))
            rank = int(hashlib.sha256(("20261015|" + token).encode()).hexdigest(), 16)
            entry = (-rank, token, row)
            if len(samples[key]) < 10:
                heapq.heappush(samples[key], entry)
            elif entry > samples[key][0]:
                heapq.heapreplace(samples[key], entry)
    needed_qids = {
        row[field]
        for heap in samples.values()
        for _, _, row in heap
        for field in ("subject_qid", "object_qid")
    }
    nodes = {}
    graph = ROOT / "GG_Data/agent_export/outputs/wwii_agent_graph_draft_v0.1.0.json"
    for node in iter_json_array(graph, "nodes"):
        qid = str(node.get("id", "")).removeprefix("wd:")
        if qid in needed_qids:
            nodes[qid] = node
    examples = []
    coverage = []
    mapping_path = OUT / "RELATION_MAPPING_TABLE_v2.1.0.csv"
    mappings = {
        (row["source"], row["source_predicate"]): row for row in read_csv(mapping_path)
    }
    endpoint_metadata = json.loads(
        (OUT / "ADDITIONAL_RELATION_ENDPOINT_METADATA_2026-10-15.json").read_text(
            encoding="utf-8"
        )
    )["entities"]
    for key, rule in sorted(by_key.items()):
        assert counts[key] == int(rule["assertions_in_current_export"])
        mapped = mappings[key]
        assert all(
            mapped[field] == rule[field]
            for field in (
                "normalized_relation_id",
                "level2_relation_id",
                "direction_to_level2",
            )
        )
        coverage.append(
            {
                "rule_id": rule["rule_id"],
                "source": key[0],
                "source_predicate": key[1],
                "assertion_count": counts[key],
                "distinct_fact_count": len(seen[key]),
                "sample_count": len(samples[key]),
                "ten_examples_available": len(seen[key]) >= 10,
                "name_description_review": rule["name_description_review"],
                "assertion_review_status": rule["assertion_review_status"],
                "assertion_review_notes": rule["assertion_review_notes"],
            }
        )
        for _, _, row in sorted(samples[key], reverse=True):
            subject, obj = original_endpoints(row)
            canonical_subject, canonical_obj = (
                (obj, subject)
                if rule["direction_to_level2"] == "reverse"
                else (subject, obj)
            )
            norm = rule["normalized_relation_id"]
            same_sources = facts.get((norm, subject, obj), set()) - {key[0]}
            reverse_candidates = inverse_ids.get(norm, set())
            found_reverse = [
                candidate
                for candidate in reverse_candidates
                if (candidate, obj, subject) in facts
            ]
            example = {
                "rule_id": rule["rule_id"],
                "source": key[0],
                "source_predicate": key[1],
                "observation_id": row["observation_id"],
                "subject_qid": subject,
                "subject_name": nodes.get(subject, {}).get("name", subject),
                "subject_focused_wikidata_label": endpoint_metadata.get(subject, {})
                .get("labels", {})
                .get("en", {})
                .get("value", ""),
                "source_relation_label": rule["relation_label"],
                "object_qid": obj,
                "object_name": nodes.get(obj, {}).get("name", obj),
                "object_focused_wikidata_label": endpoint_metadata.get(obj, {})
                .get("labels", {})
                .get("en", {})
                .get("value", ""),
                "subject_draft_type": nodes.get(subject, {}).get("type", "MISSING"),
                "object_draft_type": nodes.get(obj, {}).get("type", "MISSING"),
                "canonical_subject_qid": canonical_subject,
                "level2_relation_id": rule["level2_relation_id"],
                "canonical_object_qid": canonical_obj,
                "direction_to_level2": rule["direction_to_level2"],
                "reverse_subject_qid": canonical_obj,
                "reverse_relation_id": mapped["reverse_relation_id"],
                "reverse_relation_label": mapped["reverse_relation_label"],
                "reverse_object_qid": canonical_subject,
                "same_code_other_source_fact_sources": "|".join(sorted(same_sources)),
                "formal_reverse_counterpart_ids_present": "|".join(
                    sorted(found_reverse)
                ),
                "source_record_id": row["source_record_id"],
                "source_graph": row["source_graph"],
                "source_reference": row["source_reference"],
                "evidence_references": row["evidence_references"],
                "mapping_structure_check": "PASS_ENDPOINT_RULE_AND_REVERSIBLE_SWAP",
                "assertion_review_status": rule["assertion_review_status"],
                "assertion_review_notes": rule["assertion_review_notes"],
            }
            assert (example["reverse_object_qid"], example["reverse_subject_qid"]) == (
                canonical_subject,
                canonical_obj,
            )
            examples.append(example)
    write_csv(OUT / "ADDITIONAL_RELATION_EXAMPLES_2026-10-15.csv", examples)
    write_csv(OUT / "ADDITIONAL_RELATION_VALIDATION_2026-10-15.csv", coverage)
    summary = {
        "rules": len(rules),
        "assertions": sum(counts.values()),
        "sampled_distinct_facts": len(examples),
        "keys_with_ten_examples": sum(len(seen[key]) >= 10 for key in by_key),
        "keys_below_ten_examples": sum(len(seen[key]) < 10 for key in by_key),
        "keys_without_examples": sum(not seen[key] for key in by_key),
        "selection": "Lowest ten SHA256(seed 20261015, source, predicate, subject, object) per key",
        "nodes_found": len(nodes),
        "sample_endpoint_ids": len(needed_qids),
        "limits": [
            "A preserved identifier is not proof that the source assertion is true.",
            "Names and types are from the draft graph and can be wrong or absent.",
            "Counterpart absence is not contradictory evidence; qualifiers may constrain assertions.",
        ],
    }
    (OUT / "ADDITIONAL_RELATION_VALIDATION_SUMMARY_2026-10-15.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

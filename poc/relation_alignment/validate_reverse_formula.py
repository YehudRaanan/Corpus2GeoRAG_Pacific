"""Validate deterministic reverse-relation rules against formal contracts and graph data."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import ijson


ROOT = Path(__file__).resolve().parents[2]
MAPPING = ROOT / "GG_Data" / "mapping" / "RELATION_MAPPING_TABLE_v2.0.0.csv"
FORMAL_EVIDENCE = (
    ROOT
    / "poc"
    / "relation_alignment"
    / "deterministic_level2_mapping"
    / "formal_mapping_evidence.csv"
)
WIKIDATA_CACHE = FORMAL_EVIDENCE.with_name("wikidata_mapping_source_cache.json")
GRAPH = (
    ROOT
    / "GG_Data"
    / "agent_export"
    / "outputs"
    / "wwii_agent_graph_draft_v0.1.0.json"
)
OUT = ROOT / "poc" / "relation_alignment" / "reverse_formula_validation"


EXTRA_RULES = [
    {
        "left": "http://www.w3.org/2004/02/skos/core#broader",
        "right": "http://www.w3.org/2004/02/skos/core#narrower",
        "kind": "INVERSE",
        "source": "W3C SKOS",
        "url": "https://www.w3.org/TR/skos-reference/#S25",
        "basis": "owl:inverseOf",
    },
    {
        "left": "http://www.w3.org/2004/02/skos/core#broadMatch",
        "right": "http://www.w3.org/2004/02/skos/core#narrowMatch",
        "kind": "INVERSE",
        "source": "W3C SKOS",
        "url": "https://www.w3.org/TR/skos-reference/#S43",
        "basis": "owl:inverseOf",
    },
    {
        "left": "http://www.w3.org/2004/02/skos/core#hasTopConcept",
        "right": "http://www.w3.org/2004/02/skos/core#topConceptOf",
        "kind": "INVERSE",
        "source": "W3C SKOS",
        "url": "https://www.w3.org/TR/skos-reference/#S8",
        "basis": "owl:inverseOf",
    },
    {
        "left": "http://www.w3.org/2004/02/skos/core#related",
        "right": "http://www.w3.org/2004/02/skos/core#related",
        "kind": "SYMMETRIC",
        "source": "W3C SKOS",
        "url": "https://www.w3.org/TR/skos-reference/#S23",
        "basis": "owl:SymmetricProperty",
    },
    {
        "left": "http://www.w3.org/2004/02/skos/core#relatedMatch",
        "right": "http://www.w3.org/2004/02/skos/core#relatedMatch",
        "kind": "SYMMETRIC",
        "source": "W3C SKOS",
        "url": "https://www.w3.org/TR/skos-reference/#S44",
        "basis": "owl:SymmetricProperty",
    },
    {
        "left": "http://semanticweb.cs.vu.nl/2009/11/sem/hasSubEvent",
        "right": "http://semanticweb.cs.vu.nl/2009/11/sem/subEventOf",
        "kind": "INVERSE",
        "source": "Simple Event Model",
        "url": "https://semanticweb.cs.vu.nl/2009/11/sem/",
        "basis": "owl:inverseOf",
    },
    {
        "left": "http://schema.org/containedInPlace",
        "right": "http://schema.org/containsPlace",
        "kind": "INVERSE",
        "source": "Schema.org",
        "url": "https://schema.org/containedInPlace",
        "basis": "inverseOf",
    },
    {
        "left": "http://yago-knowledge.org/resource/isMarriedTo",
        "right": "http://yago-knowledge.org/resource/isMarriedTo",
        "kind": "SYMMETRIC",
        "source": "YAGO3",
        "url": "https://raw.githubusercontent.com/yago-naga/yago3/master/schema/relations.ttl",
        "basis": "owl:SymmetricProperty",
    },
    {
        "left": "http://rdf.muninn-project.org/ontologies/organization#rankSeniorTo",
        "right": "http://rdf.muninn-project.org/ontologies/organization#rankJuniorTo",
        "kind": "INVERSE",
        "source": "Muninn Organization ontology",
        "url": "https://rdf.muninn-project.org/ontologies/organization.owl",
        "basis": "owl:inverseOf",
    },
    {
        "left": "http://www.opengis.net/ont/geosparql#sfWithin",
        "right": "http://www.opengis.net/ont/geosparql#sfContains",
        "kind": "INVERSE",
        "source": "OGC GeoSPARQL 1.1",
        "url": "https://docs.ogc.org/is/22-047r1/22-047r1.html",
        "basis": "normative DE-9IM inverse definitions",
    },
]


def normalize_relation(value: str) -> str:
    value = value.strip().strip("<>")
    if re.fullmatch(r"P\d+", value):
        return "wd:" + value
    match = re.search(r"(?:wd:|wikidata\.org/(?:entity|prop/direct)/)(P\d+)$", value)
    if match:
        return "wd:" + match.group(1)
    return (
        value.replace("https://schema.org/", "http://schema.org/")
        .replace("https://dbpedia.org/ontology/", "http://dbpedia.org/ontology/")
        .replace(
            "http://cidoc-crm.org/cidoc-crm/",
            "http://www.cidoc-crm.org/cidoc-crm/",
        )
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_rules() -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    for row in read_csv(FORMAL_EVIDENCE):
        if row["formal_relation"] not in {"INVERSE", "SYMMETRIC"}:
            continue
        rules.append(
            {
                "left": normalize_relation(row["left_relation"]),
                "right": normalize_relation(row["right_relation"]),
                "kind": row["formal_relation"],
                "source": row["evidence_source"],
                "url": row["evidence_url"],
                "basis": (
                    "Wikidata inverse property (P1696)"
                    if row["evidence_source"] == "Wikidata"
                    else "owl:inverseOf"
                ),
            }
        )

    cache = json.loads(WIKIDATA_CACHE.read_text(encoding="utf-8"))
    for property_id, entity in cache["entities"].items():
        for claim in entity.get("claims", {}).get("P31", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if (
                claim.get("rank") != "deprecated"
                and isinstance(value, dict)
                and value.get("id") == "Q18647518"
            ):
                relation = "wd:" + property_id
                rules.append(
                    {
                        "left": relation,
                        "right": relation,
                        "kind": "SYMMETRIC",
                        "source": "Wikidata",
                        "url": f"https://www.wikidata.org/wiki/Property:{property_id}",
                        "basis": "instance of symmetric property (P31=Q18647518)",
                    }
                )
                break

    rules.extend(EXTRA_RULES)
    unique: dict[tuple[str, ...], dict[str, str]] = {}
    for rule in rules:
        key = tuple(rule[field] for field in ("left", "right", "kind", "source", "url"))
        unique[key] = rule
    return sorted(
        unique.values(), key=lambda row: (row["left"], row["right"], row["source"])
    )


def catalog_data() -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in read_csv(MAPPING):
        relation = normalize_relation(row["normalized_relation_id"])
        item = grouped.setdefault(
            relation,
            {
                "source_rows": 0,
                "occurrences": 0,
                "level2": set(),
                "labels": set(),
                "descriptions": set(),
                "policies": set(),
                "mapped_inverses": set(),
            },
        )
        item["source_rows"] += 1
        item["occurrences"] += int(row["source_occurrence_count"] or 0)
        item["level2"].add(row["level2_relation_id"])
        if row["relation_label"]:
            item["labels"].add(row["relation_label"])
        if row["relation_description"]:
            item["descriptions"].add(row["relation_description"])
        item["policies"].add(row["reverse_query_policy"])
        item["mapped_inverses"].update(
            normalize_relation(value)
            for value in row["formal_inverse_relation_ids"].split("|")
            if value
        )
    return grouped


def effective_catalog_data() -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in read_csv(MAPPING):
        relation = row["level2_relation_id"]
        item = grouped.setdefault(relation, {"occurrences": 0, "policies": set()})
        item["occurrences"] += int(row["source_occurrence_count"] or 0)
        item["policies"].add(row["reverse_query_policy"])
    return grouped


def build_contracts(rules: list[dict[str, str]]) -> tuple[dict[str, set[str]], dict]:
    candidates: dict[str, set[str]] = defaultdict(set)
    evidence: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for rule in rules:
        left, right = rule["left"], rule["right"]
        candidates[left].add(right)
        candidates[right].add(left)
        evidence[(left, right)].append(rule)
        if left != right:
            evidence[(right, left)].append(rule)
    return candidates, evidence


def graph_facts(
    relations: set[str],
) -> tuple[
    Counter[tuple[str, str, str]],
    dict[str, list[tuple[str, str, str]]],
    dict[tuple[str, str, str], dict[str, str]],
]:
    facts: Counter[tuple[str, str, str]] = Counter()
    samples: dict[str, dict[str, tuple[str, str, str]]] = defaultdict(dict)
    provenance: dict[tuple[str, str, str], dict[str, str]] = {}
    with GRAPH.open("rb") as stream:
        for edge in ijson.items(stream, "edges.item"):
            relation = normalize_relation(
                str(edge.get("attributes", {}).get("source_predicate", edge.get("type", "")))
            )
            if relation not in relations:
                continue
            fact = (str(edge["source"]), relation, str(edge["target"]))
            facts[fact] += 1
            attributes = edge.get("attributes", {})
            provenance.setdefault(
                fact,
                {
                    "edge_id": str(edge.get("id", "")),
                    "source_dataset": str(attributes.get("selected_source", "")),
                    "source_record_id": str(attributes.get("source_record_id", "")),
                },
            )
            digest = hashlib.sha256("|".join(fact).encode()).hexdigest()
            selected = samples[relation]
            selected.setdefault(digest, fact)
            if len(selected) > 10:
                del selected[max(selected)]
    ordered_samples = {
        relation: [fact for _, fact in sorted(values.items())]
        for relation, values in samples.items()
    }
    return facts, ordered_samples, provenance


def sample_node_metadata(sample_ids: set[str]) -> dict[str, tuple[str, str]]:
    nodes: dict[str, tuple[str, str]] = {}
    with GRAPH.open("rb") as stream:
        for node in ijson.items(stream, "nodes.item"):
            node_id = str(node["id"])
            if node_id in sample_ids:
                nodes[node_id] = (str(node.get("name", "")), str(node.get("type", "")))
    return nodes


def build() -> dict[str, Any]:
    rules = load_rules()
    catalog = catalog_data()
    effective_catalog = effective_catalog_data()
    candidates, evidence = build_contracts(rules)
    graph_relations = set(candidates) & set(catalog)
    facts, samples, provenance = graph_facts(graph_relations)

    graph_assertions: Counter[str] = Counter()
    graph_distinct: Counter[str] = Counter()
    explicit_reverse: Counter[str] = Counter()
    same_orientation_inverse: Counter[str] = Counter()
    for (subject, relation, object_), count in facts.items():
        graph_assertions[relation] += count
        graph_distinct[relation] += 1
        relation_candidates = candidates[relation]
        if len(relation_candidates) != 1:
            continue
        reverse = next(iter(relation_candidates))
        if len(candidates[reverse]) != 1:
            continue
        if (object_, reverse, subject) in facts:
            explicit_reverse[relation] += count
        if reverse != relation and (subject, reverse, object_) in facts:
            same_orientation_inverse[relation] += count

    contract_rows: list[dict[str, Any]] = []
    safe_reverse: dict[str, str] = {}
    for relation in sorted(candidates):
        reverse_candidates = sorted(candidates[relation])
        unique = len(reverse_candidates) == 1
        reverse = reverse_candidates[0] if unique else ""
        involutive = bool(unique and len(candidates[reverse]) == 1)
        if involutive:
            safe_reverse[relation] = reverse
        supporting = [item for target in reverse_candidates for item in evidence[(relation, target)]]
        item = catalog.get(relation, {})
        mapped_inverses = item.get("mapped_inverses", set())
        policy = item.get("policies", set())
        current_support = bool(
            involutive
            and (
                reverse in mapped_inverses
                or "FORMAL_INVERSE_AVAILABLE_FOR_QUERY_REWRITE" in policy
                or "QUERY_REWRITE_TO_LEVEL2_AND_SWAP_ENDPOINTS" in policy
                or "ALLOW_SAME_RELATION_REVERSE_SYMMETRIC" in policy
            )
        )
        if not unique or not involutive:
            status = "BLOCKED_AMBIGUOUS_NAMED_REVERSE"
        elif reverse == relation:
            status = "PASS_SYMMETRIC_SELF_REVERSE"
        else:
            status = "PASS_NAMED_INVERSE"
        assertion_count = graph_assertions[relation]
        contract_rows.append(
            {
                "relation": relation,
                "labels": "|".join(sorted(item.get("labels", set()))),
                "descriptions": "|".join(sorted(item.get("descriptions", set()))),
                "reverse_candidates": "|".join(reverse_candidates),
                "reverse_candidate_count": len(reverse_candidates),
                "formula_status": status,
                "rev_rev_equals_original": involutive,
                "catalog_present": relation in catalog,
                "catalog_source_rows": item.get("source_rows", 0),
                "catalog_occurrence_count": item.get("occurrences", 0),
                "effective_level2_ids": "|".join(sorted(item.get("level2", set()))),
                "formal_sources": "|".join(sorted({row["source"] for row in supporting})),
                "formal_bases": "|".join(sorted({row["basis"] for row in supporting})),
                "evidence_urls": "|".join(sorted({row["url"] for row in supporting})),
                "current_v2_reverse_policy": "|".join(sorted(policy)),
                "current_v2_named_reverse_ids": "|".join(sorted(mapped_inverses)),
                "current_v2_has_formal_reverse_handling": current_support,
                "graph_assertion_count": assertion_count,
                "graph_distinct_fact_count": graph_distinct[relation],
                "explicit_reverse_assertion_count": explicit_reverse[relation],
                "missing_explicit_reverse_assertion_count": (
                    assertion_count - explicit_reverse[relation] if involutive else ""
                ),
                "explicit_reverse_assertion_rate": (
                    round(explicit_reverse[relation] / assertion_count, 6)
                    if assertion_count and involutive
                    else ""
                ),
                "same_orientation_inverse_candidate_count": (
                    same_orientation_inverse[relation] if involutive else ""
                ),
                "sample_count": len(samples.get(relation, [])),
                "sample_coverage_status": (
                    "TEN"
                    if len(samples.get(relation, [])) == 10
                    else "FEWER_THAN_TEN"
                ),
            }
        )

    same_orientation_facts: dict[tuple[str, str, str, str], tuple[int, int]] = {}
    for (subject, relation, object_), count in facts.items():
        reverse = safe_reverse.get(relation, "")
        if not reverse or reverse == relation or relation > reverse:
            continue
        reverse_count = facts.get((subject, reverse, object_), 0)
        if reverse_count:
            same_orientation_facts[(relation, reverse, subject, object_)] = (
                count,
                reverse_count,
            )

    sample_ids = {
        entity
        for relation_samples in samples.values()
        for subject, _, object_ in relation_samples
        for entity in (subject, object_)
    }
    sample_ids.update(
        entity
        for _, _, subject, object_ in same_orientation_facts
        for entity in (subject, object_)
    )
    nodes = sample_node_metadata(sample_ids)
    example_rows: list[dict[str, Any]] = []
    for relation in sorted(samples):
        reverse = safe_reverse.get(relation, "")
        for rank, (subject, _, object_) in enumerate(samples[relation], start=1):
            reverse_present = bool(reverse and (object_, reverse, subject) in facts)
            same_orientation = bool(
                reverse and reverse != relation and (subject, reverse, object_) in facts
            )
            subject_name, subject_type = nodes.get(subject, ("", ""))
            object_name, object_type = nodes.get(object_, ("", ""))
            if not reverse:
                result = "NOT_TESTED_AMBIGUOUS_REVERSE"
            elif reverse_present:
                result = "EXPLICIT_REVERSE_PRESENT"
            else:
                result = "NO_EXPLICIT_REVERSE_STORED"
            example_rows.append(
                {
                    "relation": relation,
                    "reverse_relation": reverse,
                    "sample_rank": rank,
                    "subject_id": subject,
                    "subject_name": subject_name,
                    "subject_type": subject_type,
                    "object_id": object_,
                    "object_name": object_name,
                    "object_type": object_type,
                    "edge_id": provenance[(subject, relation, object_)]["edge_id"],
                    "source_dataset": provenance[(subject, relation, object_)][
                        "source_dataset"
                    ],
                    "source_record_id": provenance[(subject, relation, object_)][
                        "source_record_id"
                    ],
                    "explicit_reverse_present": reverse_present if reverse else "",
                    "same_orientation_inverse_present": same_orientation if reverse else "",
                    "validation_result": result,
                }
            )

    fields = list(contract_rows[0])
    write_csv(OUT / "reverse_contract_validation.csv", contract_rows, fields)
    write_csv(
        OUT / "reverse_example_validation.csv",
        example_rows,
        list(example_rows[0]),
    )
    same_orientation_rows: list[dict[str, Any]] = []
    for (relation, reverse, subject, object_), counts in sorted(
        same_orientation_facts.items()
    ):
        subject_name, subject_type = nodes.get(subject, ("", ""))
        object_name, object_type = nodes.get(object_, ("", ""))
        same_orientation_rows.append(
            {
                "relation": relation,
                "inverse_relation": reverse,
                "subject_id": subject,
                "subject_name": subject_name,
                "subject_type": subject_type,
                "object_id": object_,
                "object_name": object_name,
                "object_type": object_type,
                "relation_assertion_count": counts[0],
                "inverse_same_orientation_assertion_count": counts[1],
                "relation_edge_id": provenance[(subject, relation, object_)]["edge_id"],
                "relation_source_dataset": provenance[(subject, relation, object_)][
                    "source_dataset"
                ],
                "relation_source_record_id": provenance[(subject, relation, object_)][
                    "source_record_id"
                ],
                "inverse_edge_id": provenance[(subject, reverse, object_)]["edge_id"],
                "inverse_source_dataset": provenance[(subject, reverse, object_)][
                    "source_dataset"
                ],
                "inverse_source_record_id": provenance[(subject, reverse, object_)][
                    "source_record_id"
                ],
                "self_loop": subject == object_,
                "interpretation": "REVIEW_DATA_DIRECTION_NOT_FORMULA_FAILURE",
            }
        )
    write_csv(
        OUT / "same_orientation_inverse_candidates.csv",
        same_orientation_rows,
        list(same_orientation_rows[0]),
    )

    catalog_rows = [row for row in contract_rows if row["catalog_present"]]
    safe_catalog = [
        row for row in catalog_rows if str(row["formula_status"]).startswith("PASS_")
    ]
    ambiguous_catalog = [
        row
        for row in catalog_rows
        if row["formula_status"] == "BLOCKED_AMBIGUOUS_NAMED_REVERSE"
    ]
    touched_effective = {
        relation_id
        for row in catalog_rows
        for relation_id in str(row["effective_level2_ids"]).split("|")
        if relation_id
    }
    ambiguous_effective = {
        relation_id
        for row in ambiguous_catalog
        for relation_id in str(row["effective_level2_ids"]).split("|")
        if relation_id
    }
    safe_effective = touched_effective - ambiguous_effective
    handled_policies = {
        "FORMAL_INVERSE_AVAILABLE_FOR_QUERY_REWRITE",
        "QUERY_REWRITE_TO_LEVEL2_AND_SWAP_ENDPOINTS",
        "ALLOW_SAME_RELATION_REVERSE_SYMMETRIC",
    }
    handled_safe_effective = {
        relation
        for relation in safe_effective
        if effective_catalog[relation]["policies"] & handled_policies
    }
    graph_safe = [row for row in safe_catalog if row["graph_assertion_count"]]
    summary = {
        "formula": "A --P--> B entails B --REV(P)--> A; REV(REV(P)) = P",
        "formal_declaration_count": len(rules),
        "formal_relation_code_count": len(contract_rows),
        "catalog_relation_code_count": len(catalog_rows),
        "catalog_occurrence_count": sum(row["catalog_occurrence_count"] for row in catalog_rows),
        "safe_named_or_symmetric_catalog_relation_count": len(safe_catalog),
        "safe_named_or_symmetric_catalog_occurrence_count": sum(
            row["catalog_occurrence_count"] for row in safe_catalog
        ),
        "ambiguous_catalog_relation_count": len(ambiguous_catalog),
        "ambiguous_catalog_occurrence_count": sum(
            row["catalog_occurrence_count"] for row in ambiguous_catalog
        ),
        "ambiguous_catalog_relations": [row["relation"] for row in ambiguous_catalog],
        "effective_level2_relation_count": len(touched_effective),
        "effective_level2_occurrence_count": sum(
            effective_catalog[relation]["occurrences"] for relation in touched_effective
        ),
        "safe_effective_level2_relation_count": len(safe_effective),
        "safe_effective_level2_occurrence_count": sum(
            effective_catalog[relation]["occurrences"] for relation in safe_effective
        ),
        "ambiguous_effective_level2_relation_count": len(ambiguous_effective),
        "ambiguous_effective_level2_occurrence_count": sum(
            effective_catalog[relation]["occurrences"]
            for relation in ambiguous_effective
        ),
        "current_v2_handles_safe_effective_level2_count": len(
            handled_safe_effective
        ),
        "current_v2_misses_safe_effective_level2_count": len(
            safe_effective - handled_safe_effective
        ),
        "current_v2_handles_safe_relation_count": sum(
            bool(row["current_v2_has_formal_reverse_handling"]) for row in safe_catalog
        ),
        "current_v2_misses_safe_relation_count": sum(
            not bool(row["current_v2_has_formal_reverse_handling"]) for row in safe_catalog
        ),
        "graph_safe_relation_count": len(graph_safe),
        "graph_safe_assertion_count": sum(row["graph_assertion_count"] for row in graph_safe),
        "graph_explicit_reverse_assertion_count": sum(
            row["explicit_reverse_assertion_count"] for row in graph_safe
        ),
        "graph_missing_explicit_reverse_assertion_count": sum(
            row["missing_explicit_reverse_assertion_count"] for row in graph_safe
        ),
        "graph_same_orientation_inverse_candidate_count": sum(
            row["same_orientation_inverse_candidate_count"] for row in graph_safe
        ),
        "graph_same_orientation_distinct_pair_count": len(same_orientation_rows),
        "graph_same_orientation_self_loop_count": sum(
            bool(row["self_loop"]) for row in same_orientation_rows
        ),
        "relations_with_ten_examples": sum(row["sample_count"] == 10 for row in catalog_rows),
        "relations_with_fewer_than_ten_examples": sum(
            0 < row["sample_count"] < 10 for row in catalog_rows
        ),
        "relations_with_no_graph_examples": sum(
            row["sample_count"] == 0 for row in catalog_rows
        ),
        "interpretation": {
            "generic_rev": "Valid for every binary relation as an inverse expression.",
            "named_reverse": "Activate only when the formal relation graph is single-valued and involutive.",
            "missing_explicit_edge": "Not a formula failure. The reverse query view is derived from the original assertion.",
            "same_orientation_candidate": "Review candidate only; it is not automatically a contradiction.",
        },
        "inputs": {
            "mapping": str(MAPPING.relative_to(ROOT)),
            "formal_evidence": str(FORMAL_EVIDENCE.relative_to(ROOT)),
            "wikidata_cache": str(WIKIDATA_CACHE.relative_to(ROOT)),
            "wikidata_cache_retrieved_at": json.loads(
                WIKIDATA_CACHE.read_text(encoding="utf-8")
            ).get("retrieved_at_utc"),
            "graph": str(GRAPH.relative_to(ROOT)),
        },
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def self_check() -> None:
    summary = build()
    assert summary["formal_declaration_count"] > 0
    assert summary["safe_named_or_symmetric_catalog_relation_count"] > 0
    assert summary["ambiguous_catalog_relation_count"] > 0
    assert (
        summary["graph_explicit_reverse_assertion_count"]
        + summary["graph_missing_explicit_reverse_assertion_count"]
        == summary["graph_safe_assertion_count"]
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    self_check()

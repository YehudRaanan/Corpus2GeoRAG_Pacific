"""Validate the 403 EventKG/Wikidata same-identifier relation pairs.

The identifier decision is deterministic: both source rows use the same
normalized Wikidata property ID. Labels, descriptions, and sampled assertions
are validation evidence only and never create or change that identity decision.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUT = HERE / "deterministic_level2_mapping"
CONNECTIONS = OUT / "deterministic_connections.csv"
EXAMPLES = OUT / "connection_examples.csv"
FORMAL_EVIDENCE = OUT / "formal_mapping_evidence.csv"
ENTITY_METADATA = OUT / "same_identifier_entity_metadata.json"


# The EventKG label omits or changes part of the scope in the current Wikidata
# label. This is recorded as label drift. It does not change property identity.
LABEL_SCOPE_DRIFT = {
    "wd:P118",
    "wd:P1876",
    "wd:P2505",
    "wd:P2522",
    "wd:P355",
    "wd:P3975",
    "wd:P410",
    "wd:P504",
    "wd:P5012",
    "wd:P607",
    "wd:P629",
    "wd:P747",
    "wd:P749",
}


# These notes result from a manual review of the saved property description and
# every saved sample for the relation. A flagged relation has at least one clear
# contradiction. The note does not claim that every sampled assertion is bad.
SAMPLED_ASSERTION_CONTRADICTIONS = {
    "wd:P114": "The subject 'Shelling of the Mees' is an event, not an airline that belongs to KLM as an airline alliance.",
    "wd:P118": "Jürgen Stroop, Otto Ohlendorf, and Hermann Prieß point to military organizations as a league or competition.",
    "wd:P135": "Several values are political ideologies, although the property description directs political ideologies to P1142.",
    "wd:P1327": "Political relationships such as Hitler-Stalin and Stalin-Churchill are stored as business or sport partnerships.",
    "wd:P1536": "Operation Harvest Festival points to Nazi Germany as its immediate effect, although Nazi Germany predates the operation.",
    "wd:P828": "Examples such as Adolf Heusinger caused by Germany do not express an underlying cause relation.",
    "wd:P1591": "The Holocaust is treated as a trial with Adolf Hitler as its defendant.",
    "wd:P169": "Einsatzgruppen leaders are stored as corporate chief executive officers.",
    "wd:P1789": "Subhas Chandra Bose is stored as chief operating officer of the Indian National Army.",
    "wd:P208": "A person, André Gantman, is stored as the government executive body of a memorial institution.",
    "wd:P1346": "Hero City award recipients are stored as winners, although the property description explicitly excludes awardees.",
    "wd:P2568": "Adolf Hitler's rise to power is treated as a document repealed by Nazi Germany.",
    "wd:P2650": "Military units point to infantry or a security-division class as a vested interest.",
    "wd:P2789": "A military regiment points to the Mold Riots as an item with which it is physically connected.",
    "wd:P2868": "A ship points to an event, and a division points to an activity, where the property requires a role.",
    "wd:P425": "Organizations such as the British Army are used as occupations, although this property is restricted to occupations or professions.",
    "wd:P3712": "Values such as motivation, determination, and ameliorative do not state the goal of the subject 'code name'.",
    "wd:P767": "Gabriel El-Registan points to the State Anthem as a contribution target, reversing the property direction described for a creative work subject.",
    "wd:P4330": "Class and list links, such as convoy to military convoy, are stored as physical contents.",
    "wd:P520": "Military parades are treated as weapon platforms with armament.",
    "wd:P608": "The sampled values are museums or display locations, while the property requires exhibitions.",
    "wd:P6275": "Several values are copyright-status categories rather than a person or organization that represents copyright.",
    "wd:P7047": "Real wartime organizations are linked as enemies although the property description limits this relation to fictive characters or groups.",
    "wd:P8324": "Adolf Hitler is stored as the funder of the Close Combat Clasp; this assertion does not express funding.",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def label_review(row: dict[str, str]) -> tuple[str, str]:
    relation = row["left_relation"]
    left_label = row["left_label"].strip()
    right_label = row["right_label"].strip()
    if left_label.casefold() == right_label.casefold():
        return "EXACT_LABEL_MATCH", "The English labels are equal."
    if relation in LABEL_SCOPE_DRIFT:
        return (
            "EVENTKG_LABEL_SCOPE_DRIFT",
            "The EventKG label omits or changes scope that appears in the current Wikidata label or description.",
        )
    return (
        "WORDING_VARIANT_NO_CONTRADICTION",
        "The labels use different wording, but the wording does not contradict the one shared property ID.",
    )


def build() -> dict[str, object]:
    connections = [
        row
        for row in read_csv(CONNECTIONS)
        if row["left_relation"] == row["right_relation"]
    ]
    assert len(connections) == 403
    assert {(row["left_source"], row["right_source"]) for row in connections} == {
        ("EventKG", "Wikidata")
    }

    connection_ids = {row["connection_id"] for row in connections}
    examples = [
        row for row in read_csv(EXAMPLES) if row["connection_id"] in connection_ids
    ]
    examples_by_connection: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in examples:
        examples_by_connection[row["connection_id"]].append(row)

    metadata_payload = json.loads(ENTITY_METADATA.read_text(encoding="utf-8"))
    entity_metadata: dict[str, dict[str, str]] = metadata_payload["entities"]

    symmetric = {
        row["left_relation"]: row["statement_id"]
        for row in read_csv(FORMAL_EVIDENCE)
        if row["formal_relation"] == "SYMMETRIC"
        and row["left_relation"] == row["right_relation"]
    }

    pair_rows: list[dict[str, object]] = []
    example_rows: list[dict[str, object]] = []
    referenced_qids: set[str] = set()
    for row in connections:
        relation = row["left_relation"]
        pair_examples = sorted(
            examples_by_connection[row["connection_id"]],
            key=lambda item: int(item["sample_rank"]),
        )
        label_status, label_note = label_review(row)
        contradiction = SAMPLED_ASSERTION_CONTRADICTIONS.get(relation, "")
        example_status = (
            "CLEAR_CONTRADICTION_IN_AT_LEAST_ONE_SAMPLE"
            if contradiction
            else "NO_CLEAR_CONTRADICTION_FOUND_IN_SAMPLE"
        )
        counterpart_count = sum(
            item["expected_counterpart_pair_present"] == "True"
            for item in pair_examples
        )
        pair_rows.append(
            {
                "connection_id": row["connection_id"],
                "relation_id": relation,
                "eventkg_label": row["left_label"],
                "wikidata_label": row["right_label"],
                "wikidata_description": row["right_description"],
                "formal_mapping_available": "NOT_REQUIRED_IDENTICAL_GLOBAL_IDENTIFIER",
                "formal_identity_evidence": "IDENTICAL_NORMALIZED_WIKIDATA_PROPERTY_ID",
                "cross_identifier_translation": "NOT_APPLICABLE",
                "deterministic_action": "KEEP_SAME_IDENTIFIER",
                "direction": "same",
                "wikidata_symmetric_declaration": (
                    "YES" if relation in symmetric else "NO"
                ),
                "symmetric_statement_id": symmetric.get(relation, ""),
                "description_comparison": "NOT_POSSIBLE_EVENTKG_DESCRIPTION_MISSING",
                "label_comparison": label_status,
                "label_review_note": label_note,
                "example_count": len(pair_examples),
                "ten_example_status": (
                    "TEN_EXAMPLES" if len(pair_examples) == 10 else "FEWER_THAN_TEN"
                ),
                "cross_source_duplicate_fact_count": counterpart_count,
                "sample_semantic_review": example_status,
                "sample_review_note": contradiction
                or "No clear contradiction was found in the available sample. This is not proof that every assertion is correct.",
                "formal_component_conflict": row["formal_component_conflict"],
                "identity_conclusion": "VALID_SAME_IDENTIFIER",
            }
        )

        for item in pair_examples:
            subject_id = item["subject_id"]
            object_id = item["object_id"]
            if subject_id.startswith("Q"):
                referenced_qids.add(subject_id)
            if object_id.startswith("Q"):
                referenced_qids.add(object_id)
            subject_metadata = entity_metadata.get(subject_id, {})
            object_metadata = entity_metadata.get(object_id, {})
            example_rows.append(
                {
                    "connection_id": row["connection_id"],
                    "relation_id": relation,
                    "sample_rank": item["sample_rank"],
                    "sample_source_dataset": item["sample_source_dataset"],
                    "subject_id": subject_id,
                    "subject_label": subject_metadata.get("label")
                    or item["subject_name"],
                    "subject_description": subject_metadata.get("description", ""),
                    "subject_graph_type": item["subject_type"],
                    "object_id": object_id,
                    "object_label": object_metadata.get("label") or item["object_name"],
                    "object_description": object_metadata.get("description", ""),
                    "object_graph_type": item["object_type"],
                    "cross_source_duplicate_fact": item[
                        "expected_counterpart_pair_present"
                    ],
                    "relation_sample_review": example_status,
                    "relation_sample_review_note": contradiction,
                }
            )

    assert len(example_rows) == 3228
    assert all(
        1 <= len(examples_by_connection[row["connection_id"]]) <= 10
        for row in connections
    )
    assert referenced_qids <= set(entity_metadata)

    pair_fields = list(pair_rows[0])
    example_fields = list(example_rows[0])
    write_csv(OUT / "same_identifier_pair_validation.csv", pair_rows, pair_fields)
    write_csv(
        OUT / "same_identifier_example_validation.csv", example_rows, example_fields
    )

    summary = {
        "method": "Same normalized Wikidata property ID decides identity; labels, descriptions, and examples only validate data quality",
        "pair_count": len(pair_rows),
        "source_pair": ["EventKG", "Wikidata"],
        "identity_conclusion_counts": dict(
            Counter(row["identity_conclusion"] for row in pair_rows)
        ),
        "separate_cross_identifier_formal_mapping_statements": 0,
        "same_identifier_symmetric_declarations": sum(
            row["wikidata_symmetric_declaration"] == "YES" for row in pair_rows
        ),
        "description_comparison_counts": dict(
            Counter(row["description_comparison"] for row in pair_rows)
        ),
        "label_comparison_counts": dict(
            Counter(row["label_comparison"] for row in pair_rows)
        ),
        "example_count": len(example_rows),
        "example_coverage_counts": dict(
            Counter(row["ten_example_status"] for row in pair_rows)
        ),
        "sample_semantic_review_counts": dict(
            Counter(row["sample_semantic_review"] for row in pair_rows)
        ),
        "cross_source_duplicate_fact_pairs": sum(
            int(row["cross_source_duplicate_fact_count"]) > 0 for row in pair_rows
        ),
        "cross_source_duplicate_facts_in_sample": sum(
            int(row["cross_source_duplicate_fact_count"]) for row in pair_rows
        ),
        "formal_component_conflict_pairs": sum(
            row["formal_component_conflict"] == "True" for row in pair_rows
        ),
        "entity_metadata": {
            "source": metadata_payload["source"],
            "retrieved_at_utc": metadata_payload["retrieved_at_utc"],
            "entity_count": len(entity_metadata),
            "all_referenced_qids_resolved": True,
        },
        "limits": [
            "EventKG supplies no description for these 403 pairs, so a two-sided description comparison is impossible.",
            "A missing duplicate assertion in the second source is not a contradiction.",
            "No clear contradiction in ten or fewer samples is not proof that all assertions are correct.",
            "The graph sample does not include source sentences, so assertion provenance cannot be checked here.",
        ],
    }
    (OUT / "same_identifier_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

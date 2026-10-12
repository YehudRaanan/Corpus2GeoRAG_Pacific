"""Save a few EventKG examples for each relation with no declared mapping."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from run_mapping_discovery import (
    DIRECT,
    QUAD,
    REIFIED,
    part_lines,
    reified_groups,
    resource_qids,
    short,
)

HERE = Path(__file__).resolve().parent
AUDIT = HERE / "eventkg_wikidata_declared_mapping_audit" / "predicate_audit.csv"
UNRESOLVED_EDA = HERE / "unresolved_relation_eda" / "unresolved_relation_summary.csv"
OUT = HERE / "unresolved_relation_examples"
LIMIT = 3
PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
SAME_AS = "http://www.w3.org/2002/07/owl#sameAs"
LABEL_QUAD = re.compile(
    rf"^<([^>]+)> <(?:{re.escape(PREF_LABEL)}|{re.escape(RDFS_LABEL)})> "
    r'"((?:\\.|[^"\\])*)"@([\w-]+) '
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def kind(uri: str) -> str:
    local = uri.rsplit("/", 1)[-1]
    if local.startswith("event_"):
        return "event"
    if local.startswith("entity_"):
        return "entity"
    return "unknown"


def collect_examples(targets: set[str]) -> dict[str, list[dict[str, str]]]:
    examples: dict[str, list[dict[str, str]]] = defaultdict(list)

    def add(
        predicate: str,
        subject: str,
        object_: str,
        graph: str,
        format_: str,
        section: str,
        record: str = "",
    ) -> None:
        if predicate in targets and len(examples[predicate]) < LIMIT:
            examples[predicate].append(
                {
                    "relation_record_uri": record,
                    "subject_uri": subject,
                    "object_uri": object_,
                    "graph_uri": graph,
                    "graph_name": short(graph),
                    "record_format": format_,
                    "eventkg_section": section,
                }
            )

    for section in REIFIED:
        for relation, graph, role, subject, object_ in reified_groups(section):
            add(role, subject, object_, graph, "reified", section, relation or "")

    for section in DIRECT:
        for line in part_lines(section):
            match = QUAD.match(line.rstrip("\n"))
            if match:
                subject, predicate, object_, graph = match.groups()
                add(
                    predicate,
                    subject,
                    object_,
                    graph or "source_unknown",
                    "direct",
                    section,
                )
    return examples


def metadata_for(resources: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    labels: dict[str, str] = {}
    links: dict[str, set[str]] = defaultdict(set)
    for section in ("preferred_labels", "events", "entities"):
        for line in part_lines(section):
            label_match = LABEL_QUAD.match(line)
            if label_match and label_match.group(1) in resources:
                resource, escaped, language = label_match.groups()
                if resource not in labels or language == "en":
                    labels[resource] = json.loads(f'"{escaped}"')
                continue
            link_match = QUAD.match(line.rstrip("\n"))
            if (
                link_match
                and link_match.group(1) in resources
                and link_match.group(2) == SAME_AS
                and link_match.group(3).startswith(
                    (
                        "http://dbpedia.org/resource/",
                        "http://yago-knowledge.org/resource/",
                    )
                )
            ):
                links[link_match.group(1)].add(link_match.group(3))
    return labels, {
        resource: "|".join(sorted(values)) for resource, values in links.items()
    }


def build() -> dict[str, object]:
    audit_rows = [
        row
        for row in read_csv(AUDIT)
        if row["audit_status"] == "NO_DECLARED_MAPPING_FOUND"
    ]
    audit_by_predicate = {row["eventkg_predicate"]: row for row in audit_rows}
    targets = set(audit_by_predicate)
    eda_by_predicate = {
        row["source_predicate"]: row
        for row in read_csv(UNRESOLVED_EDA)
        if row["source"] == "EventKG"
    }

    resource_to_qid, _ = resource_qids()
    examples = collect_examples(targets)
    resources = {
        sample[field]
        for samples in examples.values()
        for sample in samples
        for field in ("subject_uri", "object_uri")
    }
    labels, external_links = metadata_for(resources)

    output_rows: list[dict[str, object]] = []
    coverage_rows: list[dict[str, object]] = []
    for predicate in sorted(targets):
        audit = audit_by_predicate[predicate]
        eda = eda_by_predicate.get(predicate, {})
        samples = examples.get(predicate, [])
        expected = min(LIMIT, int(audit["source_occurrence_count"]))
        coverage_rows.append(
            {
                "source_predicate": predicate,
                "source_label": audit["eventkg_label"],
                "source_occurrence_count": audit["source_occurrence_count"],
                "level2_decision": "KEEP_INDEPENDENT_SOURCE_LEVEL2",
                "independent_level2_id": predicate,
                "example_count": len(samples),
                "expected_example_count": expected,
                "coverage_status": (
                    "COMPLETE" if len(samples) == expected else "INCOMPLETE"
                ),
                "current_eda_status": eda.get("eda_status", ""),
                "level1_family": eda.get("level1_family", ""),
                "level1_candidate": eda.get("level1_candidate", ""),
                "level1_assignment_status": eda.get("level1_assignment_status", ""),
            }
        )
        for rank, sample in enumerate(samples, start=1):
            subject = sample["subject_uri"]
            object_ = sample["object_uri"]
            output_rows.append(
                {
                    "source": "EventKG",
                    "source_predicate": predicate,
                    "source_label": audit["eventkg_label"],
                    "mapping_gap_status": audit["audit_status"],
                    "level2_decision": "KEEP_INDEPENDENT_SOURCE_LEVEL2",
                    "independent_level2_id": predicate,
                    "current_eda_status": eda.get("eda_status", ""),
                    "level1_family": eda.get("level1_family", ""),
                    "level1_candidate": eda.get("level1_candidate", ""),
                    "level1_assignment_status": eda.get("level1_assignment_status", ""),
                    "source_occurrence_count": audit["source_occurrence_count"],
                    "sample_rank": rank,
                    "record_format": sample["record_format"],
                    "eventkg_section": sample["eventkg_section"],
                    "source_graph": sample["graph_name"],
                    "source_graph_uri": sample["graph_uri"],
                    "relation_record_uri": sample["relation_record_uri"],
                    "subject_uri": subject,
                    "subject_qid": resource_to_qid.get(subject, ""),
                    "subject_kind": kind(subject),
                    "subject_label": labels.get(subject, ""),
                    "subject_external_links": external_links.get(subject, ""),
                    "object_uri": object_,
                    "object_qid": resource_to_qid.get(object_, ""),
                    "object_kind": kind(object_),
                    "object_label": labels.get(object_, ""),
                    "object_external_links": external_links.get(object_, ""),
                    "raw_relation": f"<{subject}> <{predicate}> <{object_}>",
                }
            )

    incomplete = [row for row in coverage_rows if row["coverage_status"] != "COMPLETE"]
    if incomplete:
        names = ", ".join(str(row["source_predicate"]) for row in incomplete[:5])
        raise RuntimeError(
            f"Example coverage is incomplete for {len(incomplete)} relations: {names}"
        )

    status_counts = Counter(row["current_eda_status"] for row in coverage_rows)
    summary: dict[str, object] = {
        "selection_rule": "EventKG predicate audit status NO_DECLARED_MAPPING_FOUND",
        "level2_decision": "Keep every unresolved predicate as an independent source-native Level 2 relation",
        "target_relation_count": len(targets),
        "source_occurrence_sum": sum(
            int(row["source_occurrence_count"]) for row in audit_rows
        ),
        "sample_limit_per_relation": LIMIT,
        "example_row_count": len(output_rows),
        "relations_with_complete_example_coverage": len(coverage_rows),
        "relations_with_incomplete_example_coverage": len(incomplete),
        "relations_by_eda_status": dict(sorted(status_counts.items())),
        "source_data_modified": False,
    }

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "unresolved_relation_examples.csv", output_rows)
    write_csv(OUT / "relation_example_coverage.csv", coverage_rows)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))

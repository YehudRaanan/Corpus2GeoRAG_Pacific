"""Build the pre-classifier EDA for unresolved country relation pairs."""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import build_country_reference_dataset as reference
import run_country_data_availability_audit as audit

HERE = Path(__file__).resolve().parent
AUDIT_INPUT = HERE / "country_data_availability_audit/pair_audit.csv"
RESOLVED_INPUT = HERE / "country_reference_eda/resolved_relations.csv"
CATALOG_INPUT = HERE / "relation_catalog_eda/level2_relations.csv"
OUT = HERE / "classifier_candidate_eda"
REPORT = HERE / "CLASSIFIER_CANDIDATE_EDA_2026-10-11.md"
TYPE_CACHE = reference.discovery.BASE / "wikidata_country_type_hierarchy.jsonl.gz"
MAX_PARENT_DEPTH = 2
TIER_NAMES = {0: "DIRECT_P31", 1: "P279_DEPTH_1", 2: "P279_DEPTH_2"}


def item_values(entity: dict, prop: str) -> set[str]:
    values = set()
    for statement in entity.get("claims", {}).get(prop, []):
        if statement.get("rank") == "deprecated":
            continue
        value = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and value.get("id"):
            values.add(value["id"])
    return values


def fetch_type_entities(qids: set[str]) -> dict[str, dict]:
    cached = audit.load_cache(TYPE_CACHE)
    pending = [qid for qid in sorted(qids) if qid not in cached]
    for offset in range(0, len(pending), 50):
        batch = pending[offset : offset + 50]
        data = audit.fetch_json(
            audit.WIKIDATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "claims|labels|info",
                "languages": "en",
                "format": "json",
                "formatversion": 2,
            },
        )
        for qid in batch:
            cached[qid] = {
                "id": qid,
                "entity": data.get("entities", {}).get(
                    qid, {"id": qid, "missing": True}
                ),
            }
        audit.save_cache(TYPE_CACHE, cached)
        print(f"Type hierarchy: {min(offset + 50, len(pending))}/{len(pending)}")
        time.sleep(1)
    return {qid: cached[qid]["entity"] for qid in qids}


def load_type_hierarchy(direct_types: set[str]) -> dict[str, dict]:
    entities: dict[str, dict] = {}
    frontier = set(direct_types)
    for depth in range(MAX_PARENT_DEPTH + 1):
        if not frontier:
            break
        entities.update(fetch_type_entities(frontier))
        if depth == MAX_PARENT_DEPTH:
            break
        parents = {
            parent
            for qid in frontier
            for parent in item_values(entities.get(qid, {}), "P279")
        }
        frontier = parents - set(entities)
    return entities


def type_closure(
    direct_types: set[str], type_entities: dict[str, dict], max_depth: int
) -> set[str]:
    closure = set(direct_types)
    frontier = set(direct_types)
    for _ in range(max_depth):
        parents = {
            parent
            for qid in frontier
            for parent in item_values(type_entities.get(qid, {}), "P279")
        }
        frontier = parents - closure
        closure.update(frontier)
    return closure


def candidate_support(
    subject_types: set[str],
    object_types: set[str],
    seeds: list[tuple[str, str, str, set[str], set[str]]],
    type_entities: dict[str, dict],
) -> tuple[str, dict[str, int]]:
    for depth in range(MAX_PARENT_DEPTH + 1):
        subject_closure = type_closure(subject_types, type_entities, depth)
        object_closure = type_closure(object_types, type_entities, depth)
        support: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
        for subject, relation, obj, seed_subject_types, seed_object_types in seeds:
            if subject_closure & type_closure(
                seed_subject_types, type_entities, depth
            ) and object_closure & type_closure(seed_object_types, type_entities, depth):
                support[relation].add((subject, relation, obj))
        if support:
            return TIER_NAMES[depth], {
                relation: len(examples) for relation, examples in support.items()
            }
    return "NO_TYPE_MATCH", {}


def relation_metadata() -> dict[str, dict[str, str]]:
    result = {}
    for row in reference.read_csv(CATALOG_INPUT):
        code = row["canonical_level2_id"]
        if code.startswith("wd:P"):
            result[code.removeprefix("wd:")] = row
    return result


def evidence_channels(row: dict[str, str]) -> list[str]:
    channels = []
    if row["qualifier_relation_paths"]:
        channels.append("WIKIDATA_QUALIFIER")
    if row["infobox_matching_fields"]:
        channels.append("INFOBOX_FIELD")
    if row["full_article_object_link_anchors"]:
        channels.append("ENTITY_LINK")
    if row["full_article_evidence_text"]:
        channels.append("FULL_ARTICLE_SPAN")
    if row["page_anchored_evidence_text"]:
        channels.append("PAGE_ANCHORED_BODY_SPAN")
    if row["lead_evidence_status"] == "COOCCURRENCE_IN_LEAD_ONLY":
        channels.append("LEAD_SPAN")
    return channels


def classifier_input_status(row: dict[str, str]) -> str:
    if row["full_article_evidence_text"]:
        return "TEXT_SPAN_READY"
    if row["page_anchored_evidence_text"]:
        return "PAGE_ANCHORED_TEXT_READY"
    if row["lead_evidence_status"] == "COOCCURRENCE_IN_LEAD_ONLY":
        return "LEAD_SPAN_READY"
    if row["infobox_matching_fields"]:
        return "INFOBOX_ONLY"
    if row["full_article_object_link_anchors"]:
        return "ENTITY_LINK_ONLY"
    if row["qualifier_relation_paths"]:
        return "WIKIDATA_QUALIFIER_ONLY"
    return "NO_CHECKED_EVIDENCE"


def load_entities(qids: set[str]) -> dict[str, dict]:
    entities = reference.load_wikidata(qids)
    current = audit.load_cache(audit.WIKIDATA_CACHE)
    entities.update(
        {
            qid: row["entity"]
            for qid, row in current.items()
            if qid in qids and not row["entity"].get("missing")
        }
    )
    return entities


def build_seed_assertions(
    resolved: list[dict[str, str]], audit_rows: list[dict[str, str]]
) -> set[tuple[str, str, str]]:
    seeds = {
        (row["subject_qid"], row["level2_relation"], row["object_qid"])
        for row in resolved
    }
    for row in audit_rows:
        for relation in row["alternative_forward_properties"].split("|"):
            if relation:
                seeds.add((row["subject_qid"], relation, row["object_qid"]))
        for relation in row["alternative_inverse_properties"].split("|"):
            if relation:
                seeds.add((row["object_qid"], relation, row["subject_qid"]))
    return seeds


def build_infobox_relation_support(
    resolved: list[dict[str, str]], audit_rows: list[dict[str, str]]
) -> tuple[dict[str, dict[str, int]], list[dict]]:
    """Learn field-to-relation support only from structured QID-pair matches."""
    examples: dict[str, dict[str, set[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(set)
    )
    bases: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for row in audit_rows:
        relations = {
            relation
            for column in ("current_target_relations", "alternative_forward_properties")
            for relation in row[column].split("|")
            if relation
        }
        for field in row["infobox_matching_fields"].split("|"):
            if not field:
                continue
            for relation in relations:
                examples[field][relation].add(
                    (row["subject_qid"], row["object_qid"])
                )
                bases[field][relation].add("audited_structured_pair")

    pages = audit.load_cache(audit.WIKITEXT_CACHE)
    cached_resolved = [row for row in resolved if row["subject_qid"] in pages]
    object_metadata = reference.load_wikidata(
        {row["object_qid"] for row in cached_resolved}
    )
    for row in cached_resolved:
        target = object_metadata.get(row["object_qid"], {})
        target_title = target.get("enwiki_title", "")
        if not target_title:
            continue
        fields = audit.infobox_field_matches(
            pages[row["subject_qid"]].get("wikitext", ""),
            target_title,
            reference.aliases(target),
        )
        for field in fields:
            relation = row["level2_relation"]
            examples[field][relation].add(
                (row["subject_qid"], row["object_qid"])
            )
            bases[field][relation].add("resolved_reference_pair")

    support = {
        field: {
            relation: len(pairs) for relation, pairs in relation_examples.items()
        }
        for field, relation_examples in examples.items()
    }
    rows = [
        {
            "infobox_field": field,
            "level2_relation": relation,
            "structured_pair_support": count,
            "support_basis": "|".join(sorted(bases[field][relation])),
        }
        for field, relations in support.items()
        for relation, count in relations.items()
    ]
    rows.sort(
        key=lambda row: (
            row["infobox_field"],
            -row["structured_pair_support"],
            row["level2_relation"],
        )
    )
    return support, rows


def non_text_evidence(
    source: dict[str, str],
    candidates: list[str],
    field_support: dict[str, dict[str, int]],
) -> dict[str, str]:
    status = classifier_input_status(source)
    support = Counter()
    for field in source["infobox_matching_fields"].split("|"):
        support.update(field_support.get(field, {}))
    support = Counter(
        {
            relation: count
            for relation, count in support.items()
            if relation in candidates
        }
    )
    ranked = sorted(support, key=lambda relation: (-support[relation], relation))

    paths = [path for path in source["qualifier_relation_paths"].split("|") if path]
    main_properties = sorted(
        {path.removeprefix("INVERSE:").split("/", 1)[0] for path in paths}
    )
    qualifier_properties = sorted({path.split("/", 1)[1] for path in paths})
    if status == "INFOBOX_ONLY":
        review = (
            "INFOBOX_EMPIRICAL_CANDIDATES_READY"
            if ranked
            else "INFOBOX_NO_EMPIRICAL_CANDIDATE"
        )
    elif status == "ENTITY_LINK_ONLY":
        review = "ENTITY_LINK_NEEDS_EVIDENCE"
    elif status == "WIKIDATA_QUALIFIER_ONLY":
        review = "QUALIFIER_CONTEXT_READY"
        ranked = []
    else:
        review = ""

    return {
        "non_text_candidate_ids": "|".join(ranked),
        "non_text_candidate_support": json.dumps(
            {relation: support[relation] for relation in ranked if support[relation]},
            sort_keys=True,
        ),
        "qualifier_main_properties": "|".join(main_properties),
        "qualifier_properties": "|".join(qualifier_properties),
        "non_text_review_status": review,
    }


def type_labels(qids: set[str], entities: dict[str, dict]) -> str:
    return "|".join(
        entities.get(qid, {}).get("labels", {}).get("en", {}).get("value", qid)
        for qid in sorted(qids)
    )


def build() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], dict]:
    audit_rows = reference.read_csv(AUDIT_INPUT)
    resolved = reference.read_csv(RESOLVED_INPUT)
    target_rows = [
        row
        for row in audit_rows
        if row["relation_resolution_status"] == "RELATION_SEMANTICS_UNRESOLVED"
        and row["availability_status"] != "DATA_NOT_OBSERVED_IN_CHECKED_SOURCES"
    ]
    seed_assertions = build_seed_assertions(resolved, audit_rows)
    endpoint_qids = {
        qid
        for subject, _, obj in seed_assertions
        for qid in (subject, obj)
    } | {
        row[key]
        for row in target_rows
        for key in ("subject_qid", "object_qid")
    }
    entities = load_entities(endpoint_qids)

    def direct_types(qid: str) -> set[str]:
        return item_values(entities.get(qid, {}), "P31") or {"NO_P31"}

    all_direct_types = {
        type_qid
        for qid in endpoint_qids
        for type_qid in direct_types(qid)
        if type_qid != "NO_P31"
    }
    type_entities = load_type_hierarchy(all_direct_types)
    type_entities["NO_P31"] = {
        "id": "NO_P31",
        "labels": {"en": {"value": "no direct P31 type"}},
    }
    typed_seeds = [
        (subject, relation, obj, direct_types(subject), direct_types(obj))
        for subject, relation, obj in sorted(seed_assertions)
    ]
    metadata = relation_metadata()
    field_support, field_relation_rows = build_infobox_relation_support(
        resolved, audit_rows
    )
    cases = []
    for source in target_rows:
        subject_types = direct_types(source["subject_qid"])
        object_types = direct_types(source["object_qid"])
        tier, support = candidate_support(
            subject_types, object_types, typed_seeds, type_entities
        )
        candidates = sorted(support, key=lambda code: (-support[code], code))
        channels = evidence_channels(source)
        non_text = non_text_evidence(source, candidates, field_support)
        if not candidates:
            review = "NO_TYPE_MATCHED_CANDIDATE"
        elif len(candidates) > 1:
            review = "MULTIPLE_CANDIDATES"
        elif support[candidates[0]] < 2:
            review = "SINGLE_LOW_SUPPORT_CANDIDATE"
        else:
            review = "SINGLE_SUPPORTED_CANDIDATE"
        cases.append(
            {
                "subject_qid": source["subject_qid"],
                "subject_label": source["subject_label"],
                "object_qid": source["object_qid"],
                "object_label": source["object_label"],
                "subject_p31": "|".join(sorted(subject_types)),
                "subject_type_labels": type_labels(subject_types, type_entities),
                "object_p31": "|".join(sorted(object_types)),
                "object_type_labels": type_labels(object_types, type_entities),
                "evidence_channels": "|".join(channels),
                "classifier_input_status": classifier_input_status(source),
                "candidate_match_tier": tier,
                "candidate_count": len(candidates),
                "candidate_level2_ids": "|".join(candidates),
                "candidate_labels": "|".join(
                    metadata.get(code, {}).get("label", code) for code in candidates
                ),
                "candidate_level1_families": "|".join(
                    sorted(
                        {
                            metadata.get(code, {}).get(
                                "level1_family", "UNASSIGNED_REVIEW"
                            )
                            for code in candidates
                        }
                    )
                ),
                "candidate_support": json.dumps(support, sort_keys=True),
                "review_status": review,
                "infobox_matching_fields": source["infobox_matching_fields"],
                "qualifier_relation_paths": source["qualifier_relation_paths"],
                **non_text,
                "evidence_text": source["full_article_evidence_text"]
                or source["page_anchored_evidence_text"]
                or source["lead_evidence_text"],
                "wikipedia_revision_id": source["wikipedia_revision_id"],
                "classifier_selected_relations": "",
            }
        )

    type_groups: dict[tuple, list[dict]] = defaultdict(list)
    evidence_groups: Counter[tuple[str, str, str]] = Counter()
    for row in cases:
        type_groups[
            (
                row["subject_p31"],
                row["object_p31"],
                row["candidate_match_tier"],
                row["candidate_level2_ids"],
            )
        ].append(row)
        evidence_groups[
            (
                row["classifier_input_status"],
                row["candidate_match_tier"],
                row["review_status"],
            )
        ] += 1
    type_group_rows = [
        {
            "subject_p31": key[0],
            "subject_type_labels": members[0]["subject_type_labels"],
            "object_p31": key[1],
            "object_type_labels": members[0]["object_type_labels"],
            "candidate_match_tier": key[2],
            "candidate_level2_ids": key[3],
            "pair_count": len(members),
            "text_span_ready_pairs": sum(
                row["classifier_input_status"]
                in {
                    "TEXT_SPAN_READY",
                    "PAGE_ANCHORED_TEXT_READY",
                    "LEAD_SPAN_READY",
                }
                for row in members
            ),
        }
        for key, members in type_groups.items()
    ]
    type_group_rows.sort(key=lambda row: (-row["pair_count"], row["subject_p31"]))
    evidence_group_rows = [
        {
            "classifier_input_status": key[0],
            "candidate_match_tier": key[1],
            "review_status": key[2],
            "pair_count": count,
        }
        for key, count in sorted(
            evidence_groups.items(), key=lambda item: (-item[1], item[0])
        )
    ]

    seed_counts = Counter(relation for _, relation, _ in seed_assertions)
    candidate_counts = Counter(
        relation for row in cases for relation in row["candidate_level2_ids"].split("|") if relation
    )
    relation_rows = []
    for relation in sorted(seed_counts, key=lambda code: (-seed_counts[code], code)):
        meta = metadata.get(relation, {})
        relation_rows.append(
            {
                "level2_relation": relation,
                "label": meta.get("label", relation),
                "level1_family": meta.get("level1_family", "UNASSIGNED_REVIEW"),
                "description": meta.get("description", ""),
                "structured_seed_assertions": seed_counts[relation],
                "unresolved_candidate_pairs": candidate_counts[relation],
            }
        )

    status_counts = Counter(row["classifier_input_status"] for row in cases)
    tier_counts = Counter(row["candidate_match_tier"] for row in cases)
    review_counts = Counter(row["review_status"] for row in cases)
    candidate_count_distribution = Counter(row["candidate_count"] for row in cases)
    text_ready = [
        row
        for row in cases
        if row["classifier_input_status"]
        in {
            "TEXT_SPAN_READY",
            "PAGE_ANCHORED_TEXT_READY",
            "LEAD_SPAN_READY",
        }
    ]
    non_text_status_counts = Counter(
        row["non_text_review_status"]
        for row in cases
        if row["non_text_review_status"]
    )
    summary = {
        "unresolved_pairs_with_checked_evidence": len(cases),
        "structured_seed_assertions": len(seed_assertions),
        "structured_seed_relations": len(seed_counts),
        "candidate_relation_ids": sorted(seed_counts),
        "candidate_match_tiers": dict(tier_counts),
        "review_status_counts": dict(review_counts),
        "candidate_count_distribution": {
            str(count): pairs
            for count, pairs in sorted(candidate_count_distribution.items())
        },
        "classifier_input_status_counts": dict(status_counts),
        "pairs_with_one_or_more_candidates": sum(
            bool(row["candidate_level2_ids"]) for row in cases
        ),
        "pairs_without_type_matched_candidates": sum(
            not row["candidate_level2_ids"] for row in cases
        ),
        "pairs_with_one_candidate": sum(row["candidate_count"] == 1 for row in cases),
        "pairs_with_multiple_candidates": sum(
            row["candidate_count"] > 1 for row in cases
        ),
        "exact_type_pair_candidate_pairs": tier_counts["DIRECT_P31"],
        "hierarchy_expanded_candidate_pairs": tier_counts["P279_DEPTH_1"]
        + tier_counts["P279_DEPTH_2"],
        "text_span_ready_pairs": len(text_ready),
        "text_span_ready_with_candidates": sum(
            bool(row["candidate_level2_ids"]) for row in text_ready
        ),
        "text_span_ready_multiple_candidates": sum(
            row["candidate_count"] > 1 for row in text_ready
        ),
        "text_span_ready_single_supported_candidate": sum(
            row["review_status"] == "SINGLE_SUPPORTED_CANDIDATE"
            for row in text_ready
        ),
        "non_text_evidence_pairs": len(cases) - len(text_ready),
        "non_text_review_status_counts": dict(non_text_status_counts),
        "infobox_field_relation_rows": len(field_relation_rows),
        "infobox_pairs_with_empirical_candidates": non_text_status_counts[
            "INFOBOX_EMPIRICAL_CANDIDATES_READY"
        ],
        "infobox_pairs_without_empirical_candidates": non_text_status_counts[
            "INFOBOX_NO_EMPIRICAL_CANDIDATE"
        ],
        "qualifier_context_pairs": non_text_status_counts["QUALIFIER_CONTEXT_READY"],
        "entity_link_pairs_needing_evidence": non_text_status_counts[
            "ENTITY_LINK_NEEDS_EVIDENCE"
        ],
        "type_pair_groups": len(type_group_rows),
        "classifier_run": False,
        "selection_rule": (
            "Use the narrowest P31/P279 tier with structured examples. Candidate "
            "support ranks options but does not select a relation."
        ),
    }
    return (
        cases,
        type_group_rows,
        evidence_group_rows,
        relation_rows,
        field_relation_rows,
        summary,
    )


def write_report(summary: dict, relations: list[dict]) -> None:
    lines = [
        "# Classifier candidate EDA",
        "",
        "Date: 2026-10-11",
        "",
        "## Scope",
        "",
        f"The EDA covers **{summary['unresolved_pairs_with_checked_evidence']:,}** unresolved pairs that have checked evidence.",
        "It uses resolved structured pairs only to create possible Level 2 choices.",
        "It does not select a relation and does not run a classifier.",
        "The Wikipedia page QID defines the subject. A page-anchored evidence",
        "sentence therefore needs to identify only the object in the article body.",
        "",
        "## Candidate construction",
        "",
        f"- **{summary['structured_seed_assertions']:,}** unique structured seed assertions.",
        f"- **{summary['structured_seed_relations']:,}** possible Level 2 relation values.",
        "- Compare direct Wikidata `P31` endpoint types first.",
        "- If no candidate exists, expand through `P279` for at most two levels.",
        "- Stop at the first level that produces candidates.",
        "- Keep all relations supported at that level; support count ranks them only.",
        "",
        "## Main results",
        "",
        f"- **{summary['pairs_with_one_or_more_candidates']:,}** pairs have one or more type-matched candidates.",
        f"- **{summary['pairs_without_type_matched_candidates']:,}** pairs have no type-matched candidate.",
        f"- **{summary['pairs_with_one_candidate']:,}** pairs have one candidate.",
        f"- **{summary['pairs_with_multiple_candidates']:,}** pairs have several candidates.",
        f"- **{summary['exact_type_pair_candidate_pairs']:,}** pairs match direct `P31` types.",
        f"- **{summary['hierarchy_expanded_candidate_pairs']:,}** pairs need broader `P279` types.",
        "",
        "## Classifier gate",
        "",
        f"- **{summary['text_span_ready_pairs']:,}** pairs have the required complete sentence or paragraph.",
        f"- **{summary['text_span_ready_with_candidates']:,}** of them also have a type-matched candidate list.",
        f"- **{summary['text_span_ready_multiple_candidates']:,}** text-ready pairs need the classifier to choose among several candidates.",
        f"- **{summary['text_span_ready_single_supported_candidate']:,}** text-ready pairs have one candidate with at least two seed examples.",
        f"- **{summary['non_text_evidence_pairs']:,}** pairs have only structured, infobox, or link evidence and are outside the text-classifier input contract.",
        "",
        "## Non-text evidence",
        "",
        f"- **{summary['infobox_pairs_with_empirical_candidates']:,}** infobox pairs have relation candidates learned from structured QID-pair matches.",
        f"- **{summary['infobox_pairs_without_empirical_candidates']:,}** infobox pairs have no empirical field mapping in the checked data.",
        f"- **{summary['qualifier_context_pairs']:,}** qualifier pairs preserve the main property and qualifier property.",
        f"- **{summary['entity_link_pairs_needing_evidence']:,}** pairs remain link-only.",
        "- These signals rank candidates. They do not resolve a relation.",
        "",
        "## Evidence readiness",
        "",
        "| Input status | Pairs |",
        "|---|---:|",
        *[
            f"| `{status}` | {count:,} |"
            for status, count in sorted(
                summary["classifier_input_status_counts"].items()
            )
        ],
        "",
        "## Candidate review status",
        "",
        "| Status | Pairs |",
        "|---|---:|",
        *[
            f"| `{status}` | {count:,} |"
            for status, count in sorted(summary["review_status_counts"].items())
        ],
        "",
        "## Possible Level 2 values",
        "",
        "| Relation | Label | Level 1 | Seed assertions | Candidate pairs |",
        "|---|---|---|---:|---:|",
        *[
            f"| `{row['level2_relation']}` | {row['label']} | `{row['level1_family']}` | {row['structured_seed_assertions']:,} | {row['unresolved_candidate_pairs']:,} |"
            for row in relations
        ],
        "",
        "## Limits before classification",
        "",
        "- Type compatibility creates an allowed list. It does not prove a relation.",
        "- A broad `P279` match can add unrelated choices.",
        "- A candidate with one seed example is weak.",
        "- A page-anchored sentence can discuss another entity on the page. The",
        "  classifier must be allowed to return `UNRESOLVED`.",
        "- An infobox field or entity link is not a complete co-appearance text span.",
        "- `NO_TYPE_MATCHED_CANDIDATE` means that the seed data do not cover the type pair.",
        "",
        "## Files",
        "",
        "- `classifier_candidate_eda/cases.csv`",
        "- `classifier_candidate_eda/type_pair_groups.csv`",
        "- `classifier_candidate_eda/evidence_groups.csv`",
        "- `classifier_candidate_eda/candidate_relations.csv`",
        "- `classifier_candidate_eda/infobox_field_relations.csv`",
        "- `classifier_candidate_eda/summary.json`",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    (
        cases,
        type_groups,
        evidence_groups,
        relations,
        field_relations,
        summary,
    ) = build()
    OUT.mkdir(parents=True, exist_ok=True)
    reference.write_csv(OUT / "cases.csv", cases, list(cases[0]))
    reference.write_csv(
        OUT / "type_pair_groups.csv", type_groups, list(type_groups[0])
    )
    reference.write_csv(
        OUT / "evidence_groups.csv", evidence_groups, list(evidence_groups[0])
    )
    reference.write_csv(
        OUT / "candidate_relations.csv", relations, list(relations[0])
    )
    reference.write_csv(
        OUT / "infobox_field_relations.csv",
        field_relations,
        list(field_relations[0]),
    )
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_report(summary, relations)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

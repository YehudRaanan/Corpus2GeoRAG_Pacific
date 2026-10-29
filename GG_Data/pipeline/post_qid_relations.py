"""Lossless native assertions for a typed post-QID scope; no acquisition.

Inputs must be complete Wikidata records, with independently verified retrieval
coverage. Candidate discovery completeness cannot be inferred from these rows.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re

from GG_Data.mapping.assertion_exclusions import exclusion_reason, load_exclusions
from GG_Data.pipeline.relations import SourceException, populate, statement_time

POLICY = "post-qid-directed-all-native-v1"


def validate_mapping(rule: dict, predicate: str) -> None:
    if rule["direction_to_level2"] not in {"same", "reverse"} or (
        rule["formal_component_conflict"] != "False"
        and not (
            rule["level2_relation_id"] == predicate
            and rule["direction_to_level2"] == "same"
            and rule.get("level2_decision")
            == "RETAIN_SOURCE_ID_BLOCK_FORMAL_TRANSLATION"
        )
    ):
        raise SourceException("Conflicting mapping", source_predicate=predicate)


def temporal_evidence(statement: dict) -> dict:
    """Keep legacy scalar selection when supported, raw evidence otherwise."""
    try:
        return statement_time(statement)
    except SourceException as error:
        raw, precision = {}, {}
        for name, prop in (("from", "P580"), ("to", "P582"), ("point", "P585")):
            values = [
                s.get("datavalue", {}).get("value")
                for s in statement.get("qualifiers", {}).get(prop, [])
            ]
            raw[name] = sorted(
                {v["time"] for v in values if isinstance(v, dict) and v.get("time")}
            )
            precision[name] = sorted(
                {
                    v["precision"]
                    for v in values
                    if isinstance(v, dict) and v.get("precision") is not None
                }
            )
        return dict(
            time_from=None,
            time_to=None,
            time_point=None,
            time_precision=precision,
            raw_time_values=raw,
            time_status="AMBIGUOUS",
            time_selection=dict(
                policy_version=POLICY,
                original_pre_1900_end=False,
                decisions={},
                exception=error.case,
            ),
        )


def build_relations(
    records: dict[str, dict],
    entities: list[dict],
    mapping: dict,
    reverse_lookup: dict,
    *,
    sources: dict[str, list],
) -> dict:
    """Return stored directed rows and complete assertion accounting.

    Scope is QID membership, never the typed-row Cartesian product. Unknown
    properties retain their native identifier and an explicit synthetic inverse.
    No relevance, period, MISC or degree-based retention applies.
    """
    scope = {
        r["entity_id"] for r in entities if re.fullmatch(r"Q[1-9]\d*", r["entity_id"])
    }
    missing = scope - records.keys()
    if missing:
        raise SourceException("Missing full source records", missing=sorted(missing))
    mapping, reverse_lookup = dict(mapping), dict(reverse_lookup)
    exclusions = load_exclusions()
    retained, excluded, unknown = [], [], []
    seen, counts = {}, Counter()
    for subject in sorted(scope):
        record = records[subject]
        if record.get("id") != subject or not isinstance(record.get("claims"), dict):
            raise SourceException("Invalid full native record", subject_qid=subject)
        if subject not in sources or not sources[subject]:
            raise SourceException(
                "Missing native record provenance", subject_qid=subject
            )
        counts["source_qids"] += 1
        for prop, statements in record["claims"].items():
            if not isinstance(statements, list):
                raise SourceException("Invalid native claims list", subject_qid=subject)
            for statement in statements:
                counts["raw_claims"] += 1
                snak = statement.get("mainsnak", {})
                value = snak.get("datavalue", {}).get("value")
                if not isinstance(value, dict) or value.get("entity-type") != "item":
                    counts["non_item_claims"] += 1
                    continue
                target = value.get("id") or f"Q{value.get('numeric-id', '')}"
                if target not in scope:
                    counts["outside_scope"] += 1
                    continue
                case = dict(
                    subject_qid=subject,
                    subject_name=subject,
                    object_qid=target,
                    source_predicate=f"wd:{prop}",
                    source_record_id=statement.get("id"),
                    raw_statement=statement,
                    source_record=sources[subject],
                )
                if (
                    not re.fullmatch(r"P[1-9]\d*", prop)
                    or snak.get("property") != prop
                    or snak.get("snaktype") != "value"
                    or snak.get("datatype") != "wikibase-item"
                    or not statement.get("id")
                    or statement.get("rank")
                    not in {"normal", "preferred", "deprecated"}
                    or (
                        "numeric-id" in value and value["numeric-id"] != int(target[1:])
                    )
                ):
                    raise SourceException("Unexpected native statement shape", **case)
                sid = statement["id"]
                if sid in seen:
                    if seen[sid] != case:
                        raise SourceException(
                            "Conflicting repeated statement ID", **case
                        )
                    counts["repeated_retrievals"] += 1
                    continue
                seen[sid] = dict(case)
                reason = exclusion_reason(
                    "Wikidata", {**case, "predicate": f"wd:{prop}"}, exclusions
                )
                if reason:
                    excluded.append(dict(**case, reason=reason))
                    continue
                case.update(temporal_evidence(statement))
                rule = mapping.get(("Wikidata", f"wd:{prop}"))
                if rule is None:
                    predicate = f"wd:{prop}"
                    rule = dict(
                        direction_to_level2="same",
                        level1_family="UNRESOLVED",
                        level1_assignment_status="NOT_ASSIGNED",
                        level2_relation_id=predicate,
                        level2_relation_label=predicate,
                        relation_map_version=POLICY,
                        formal_component_conflict="False",
                    )
                    mapping["Wikidata", predicate] = rule
                    for key, inverse in (
                        (predicate, "inverse:" + predicate),
                        ("inverse:" + predicate, predicate),
                    ):
                        reverse_lookup[key] = dict(
                            output_reverse_relation_id=inverse,
                            output_reverse_relation_label=inverse,
                            endpoint_action="SWAP_SOURCE_TARGET",
                            synthetic=True,
                        )
                if rule["relation_map_version"] == POLICY:
                    unknown.append(case)
                validate_mapping(rule, f"wd:{prop}")
                retained.append(case)
    rows = []
    for base in populate(retained, mapping):
        oid = base["observation_id"]
        base.update(
            base_assertion_id=oid,
            source_assertion_id=base["source_record_id"],
            derived=False,
            derived_direction="FORWARD",
            source_edge_id=None,
            relation_population_policy=POLICY,
        )
        if base["input_assertion"]["mapping"]["relation_map_version"] == POLICY:
            base["mapping_origin"] = "native_identifier_preserved"
        rows.append(base)
        if base["subject_entity_id"] == base["object_entity_id"]:
            continue
        rid = base["level2_relation"]
        lookup = reverse_lookup.get(rid)
        if (
            not lookup
            or lookup.get("endpoint_action") != "SWAP_SOURCE_TARGET"
            or reverse_lookup.get(lookup["output_reverse_relation_id"], {}).get(
                "output_reverse_relation_id"
            )
            != rid
        ):
            raise SourceException(
                "Missing or non-involutive reverse mapping", relation=rid
            )
        reverse = deepcopy(base)
        reverse.update(
            observation_id=oid + "::REVERSE",
            source_edge_id=oid,
            subject_entity_id=base["object_entity_id"],
            object_entity_id=base["subject_entity_id"],
            level2_relation=lookup["output_reverse_relation_id"],
            level2_label=lookup["output_reverse_relation_label"],
            derived=True,
            derived_direction="REVERSE",
        )
        reverse["synthetic_inverse"] = lookup.get("synthetic", False)
        rows.append(reverse)
    counts.update(
        base_assertions=len(retained),
        directed_rows=len(rows),
        excluded_assertions=len(excluded),
        unknown_mapping_assertions=len(unknown),
        unique_in_scope_assertions=len(seen),
    )
    return dict(
        status="RELATIONS_READY",
        policy_version=POLICY,
        relations=rows,
        excluded=excluded,
        unknown_predicates=unknown,
        counts=dict(counts),
    )


def select_events(
    records: dict[str, dict],
    corpus_qids: set[str],
    occurrence_types: set[str],
    mapping: dict,
) -> dict:
    """Select from provided full records only; no recursive discovery.

    The caller must supply the pinned occurrence hierarchy and establish that
    discovery covered both native directions for the complete corpus scope.
    This function reports local eligibility, never discovery completeness.
    """
    from GG_Data.pipeline.event_population import verify_recognition

    candidates = {
        qid
        for qid, record in records.items()
        if verify_recognition(record, occurrence_types)
    }
    scope = corpus_qids | candidates
    # In-memory provenance identifies this input, not a claimed remote source.
    # Reuse the source scanner with native identity mappings: exact exclusions
    # are applied before neighbour counting, without requiring export inverses.
    result = build_relations(
        records,
        [{"entity_id": q} for q in scope],
        {},
        {},
        sources={q: [{"input": "provided_full_records", "qid": q}] for q in records},
    )
    neighbours = {q: set() for q in candidates}
    for row in result["relations"]:
        if row["derived"]:
            continue
        rule = mapping.get(("Wikidata", row["selected_source_predicate"]))
        if rule:
            validate_mapping(rule, row["selected_source_predicate"])
        subject, target = row["subject_entity_id"], row["object_entity_id"]
        if subject in candidates and target in corpus_qids and subject != target:
            neighbours[subject].add(target)
        if target in candidates and subject in corpus_qids and subject != target:
            neighbours[target].add(subject)
    decisions = [
        dict(
            qid=q,
            linked_corpus_qids=sorted(neighbours[q]),
            keep_event=len(neighbours[q]) >= 2,
        )
        for q in sorted(candidates)
    ]
    return dict(
        selected_event_qids=[d["qid"] for d in decisions if d["keep_event"]],
        decisions=decisions,
        discovery_completeness="NOT_ESTABLISHED",
    )


def export_stored_relations(relations: list[dict]) -> list[dict]:
    """Project each stored directed row once; never generate reverse views."""
    edges, seen = [], set()
    for row in relations:
        oid = row["observation_id"]
        if oid in seen:
            raise SourceException("Duplicate stored directed row", observation_id=oid)
        seen.add(oid)
        if row.get("relation_population_policy") != POLICY:
            raise SourceException(
                "Expected stored-direction policy", observation_id=oid
            )
        edges.append(
            dict(
                id=oid,
                source=row["subject_entity_id"],
                target=row["object_entity_id"],
                type=row["level2_relation"],
                relation_label=row["level2_label"],
                relation_family=row["level1_relation"],
                count=row["count"],
                start_date=row["time_from"] or None,
                end_date=row["time_to"] or None,
                point_date=row["time_point"] or None,
                base_assertion_id=row["base_assertion_id"],
                source_assertion_id=row["source_assertion_id"],
                source_record_id=row["source_record_id"],
                selected_source_predicate=row["selected_source_predicate"],
                derived=row["derived"],
                derived_direction=row["derived_direction"],
                source_edge_id=row["source_edge_id"],
                relation_population_policy=POLICY,
            )
        )
    return edges

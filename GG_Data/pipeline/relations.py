"""Daniel-QID Relations population: population S2T 8 and ERD 6.

Read the accepted Entities records only. No network client, entity extraction,
rematching or event discovery is used. Stop at the first unexpected source case.
Event/Daniel links are a later step; this is not a complete Relations release.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

import ijson

from GG_Data.mapping.assertion_exclusions import exclusion_reason, load_exclusions
from GG_Data.mapping import build_relation_mapping_v2_1 as catalog
from GG_Data.mapping.build_relation_mapping_v2_1 import OUT, read_csv, write_csv
from GG_Data.pipeline.entities import acquire_missing
from GG_Data.pipeline.poc import ROOT, digest, read_json

LOG = logging.getLogger(__name__)
ACCEPTED_ENTITIES_SHA = (
    "a4b967188c7247996309e53dba9851208d8d8e1e69c21d79f7afb1cc35c252e4"
)
BASE_MAPPING_SHA = "8ecdc0095d10ec1fc24dfb82510473faef42b896c126b76cb0daeb233b301821"
TIME_POLICY = "relation-date-selection-v1.1.0"
NATIVE_RULES = OUT / "ADDITIONAL_NATIVE_RELATION_RULES_2026-10-20.csv"
PROPERTY_METADATA = (
    ROOT / "poc/relation_alignment/relation_catalog_eda/wikidata_property_metadata.json"
)


class SourceException(ValueError):
    """A business/data exception must be shown, not repaired automatically."""

    def __init__(self, reason: str, **case: object):
        self.case = dict(reason=reason, **case)
        super().__init__(f"{reason}: {case.get('source_record_id', '')}")


def statement_time(statement: dict) -> dict:
    """Population S2T 8: approved start/end selection, 20 October 2026.

    Start: earliest supplied value from 1900; all earlier -> derived year 1900.
    End: latest supplied value. Preserve original snaks, precision and calendars.
    User correction: when the latest end precedes 1900, keep the original
    supplied dates without the start floor; never exclude on this date alone.
    No point-date selection or reversed-interval repair has been approved.
    """
    selected, raw, precisions, decisions = {}, {}, {}, {}

    def date_parts(value: str) -> tuple[int, ...]:
        match = re.fullmatch(
            r"([+-]\d+)-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z", value
        )
        if not match:
            raise SourceException("Unsupported native date format", value=value)
        return tuple(map(int, match.groups()))

    # Inspect the end first so a historical relation keeps its original start.
    for name, prop in (("to", "P582"), ("from", "P580"), ("point", "P585")):
        snaks = statement.get("qualifiers", {}).get(prop, [])
        values, precision = [], []
        for snak in snaks:
            value = snak.get("datavalue", {}).get("value")
            if isinstance(value, dict) and value.get("time"):
                values.append(value["time"])
                if value.get("precision") is not None:
                    precision.append(int(value["precision"]))
        raw[name] = sorted(set(values))
        selected[name] = raw[name][0] if len(raw[name]) == 1 else ""
        precisions[name] = sorted(set(precision))
        if raw[name] and name in {"from", "to"}:
            calendars = {
                s["datavalue"]["value"].get("calendarmodel")
                for s in snaks
                if isinstance(s.get("datavalue", {}).get("value"), dict)
                and s["datavalue"]["value"].get("time")
            }
            if len(calendars) > 1:
                raise SourceException(
                    "Different calendars require consultation",
                    property=prop,
                    calendars=sorted(str(c) for c in calendars),
                )
            candidates = raw[name]
            historical = (
                name == "from"
                and bool(selected.get("to"))
                and date_parts(selected["to"])[0] < 1900
            )
            if name == "from":
                if not historical:
                    candidates = [v for v in candidates if date_parts(v)[0] >= 1900]
                selected[name] = (
                    min(candidates, key=date_parts)
                    if candidates
                    else "+1900-00-00T00:00:00Z"
                )
            else:
                selected[name] = max(candidates, key=date_parts)
            decisions[name] = dict(
                value=selected[name],
                rule=(
                    "ORIGINAL_PRE_1900_END"
                    if historical
                    else (
                        "EARLIEST_FROM_1900"
                        if name == "from" and candidates
                        else "YEAR_1900_FLOOR" if name == "from" else "LATEST_END"
                    )
                ),
                derived=name == "from" and not candidates,
                selected_precision=(
                    [9]
                    if name == "from" and not candidates
                    else sorted(
                        {
                            s["datavalue"]["value"]["precision"]
                            for s in snaks
                            if isinstance(s.get("datavalue", {}).get("value"), dict)
                            and s["datavalue"]["value"].get("time") == selected[name]
                            and s["datavalue"]["value"].get("precision") is not None
                        }
                    )
                ),
            )
    start, end, point = (selected[k] for k in ("from", "to", "point"))
    first, last = date_parts(start) if start else None, date_parts(end) if end else None
    status = (
        "CONFLICT"
        if first and last and first > last
        else (
            "MULTIPLE"
            if any(len(v) > 1 for v in raw.values())
            else (
                "DIRECT"
                if point or (start and end)
                else "PARTIAL" if start or end else "NONE"
            )
        )
    )
    return dict(
        time_from=start,
        time_to=end,
        time_point=point,
        time_precision=precisions,
        raw_time_values=raw,
        time_status=status,
        time_selection=dict(
            policy_version=TIME_POLICY,
            original_pre_1900_end=bool(last and last[0] < 1900),
            decisions=decisions,
        ),
    )


def scan(
    entities: list[dict], qids: set[str], mapping: dict
) -> tuple[list, list, Counter]:
    """Inspect each source QID once; typed rows never multiply assertions.

    Scope and the 14 guarded exclusions precede mapping. All ranks remain
    eligible. Non-item/out-of-scope claims remain in immutable Entities evidence.
    """
    exclusions = load_exclusions()
    seen_entities, seen_statements = {}, {}
    retained, excluded, counts = [], [], Counter()
    for row in entities:
        subject = row["entity_id"]
        if subject not in qids:
            continue
        record = row["raw_reference"]["full"]["entity"]
        if record.get("id") != subject or "claims" not in record:
            raise SourceException("Invalid full source record", subject_qid=subject)
        if subject in seen_entities:
            if seen_entities[subject] != record:
                raise SourceException(
                    "Typed rows have different source records", subject_qid=subject
                )
            continue
        seen_entities[subject] = record
        counts["source_qids_checked"] += 1
        for prop, statements in record["claims"].items():
            for statement in statements:
                counts["raw_claims_checked"] += 1
                snak = statement.get("mainsnak", {})
                value = snak.get("datavalue", {}).get("value")
                if not isinstance(value, dict) or value.get("entity-type") != "item":
                    counts["non_item_claims_in_raw_evidence"] += 1
                    continue
                target = value.get("id") or f"Q{value.get('numeric-id', '')}"
                if target not in qids:
                    counts["item_claims_outside_daniel_population"] += 1
                    continue
                case = dict(
                    subject_qid=subject,
                    subject_name=row["name"],
                    object_qid=target,
                    source_predicate=f"wd:{prop}",
                    source_record_id=statement.get("id"),
                    raw_statement=statement,
                    source_record=row["sources"],
                )
                counts["in_scope_statements_checked"] += 1
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
                if sid in seen_statements:
                    if seen_statements[sid] != case:
                        raise SourceException(
                            "Conflicting repeated statement ID", **case
                        )
                    counts["repeated_retrievals"] += 1
                    continue
                seen_statements[sid] = case
                reason = exclusion_reason(
                    "Wikidata",
                    {**case, "predicate": case["source_predicate"]},
                    exclusions,
                )
                if reason:
                    excluded.append(dict(**case, reason=reason))
                    counts["excluded_statements"] += 1
                    continue
                try:
                    time = statement_time(statement)
                except SourceException as error:
                    raise SourceException(
                        error.case["reason"], **case, temporal_exception=error.case
                    ) from error
                if (
                    time["time_status"] == "CONFLICT"
                    or len(time["raw_time_values"]["point"]) > 1
                ):
                    raise SourceException(
                        "Temporal values require consultation",
                        **case,
                        temporal_evidence=time,
                    )
                rule = mapping.get(("Wikidata", case["source_predicate"]))
                # Existing catalog decisions can block formal translation while
                # explicitly retaining the native ID. That is a settled mapping,
                # not an unresolved source-key conflict (S2T 8: existing first).
                if rule and (
                    rule["direction_to_level2"] not in {"same", "reverse"}
                    or (
                        rule["formal_component_conflict"] != "False"
                        and not (
                            rule["level2_relation_id"] == case["source_predicate"]
                            and rule["direction_to_level2"] == "same"
                            and rule["level2_decision"]
                            == "RETAIN_SOURCE_ID_BLOCK_FORMAL_TRANSLATION"
                        )
                    )
                ):
                    raise SourceException("Conflicting mapping", **case, mapping=rule)
                retained.append(dict(**case, **time))
                if time["time_selection"]["original_pre_1900_end"]:
                    counts["retained_original_pre_1900_end"] += 1
                counts[f"rank.{statement['rank']}"] += 1
                counts[f"time.{time['time_status']}"] += 1
    if seen_entities.keys() != qids:
        raise SourceException(
            "Full source QID coverage differs",
            missing=sorted(qids - seen_entities.keys()),
        )
    counts["retained_statements"] = len(retained)
    return retained, excluded, counts


def read_entities(path: Path) -> list[dict]:
    # ijson avoids a second large uncompressed text copy. No external retrieval.
    with gzip.open(path, "rb") as stream:
        return list(ijson.items(stream, "item", use_float=True))


def extend_mapping(
    statements: list[dict], mapping: dict, output: Path, reference: dict
) -> tuple:
    """S2T 8: actual native statements only; no family or semantic inference.

    Reuse the existing builder and cumulative parameters. POC v2.1.2 belongs
    to this pinned sample; historical catalogs and decisions stay immutable.
    """
    missing = defaultdict(list)
    for case in statements:
        key = ("Wikidata", case["source_predicate"])
        if key not in mapping:
            missing[key[1]].append(case)
    if not missing:
        return mapping, OUT, "relation-map-v2.1.1", []
    properties = read_json(PROPERTY_METADATA)["properties"]
    extra = read_json(catalog.ADDITIONAL_METADATA)["entities"]
    # Explicit approval after the P10888 stop: retrieve/cache only missing
    # property names from the agreed pinned BigQuery source, not another API.
    unlabeled = {
        p.removeprefix("wd:")
        for p in missing
        if not any(
            r["level2_relation_id"] == p and r["level2_relation_label"]
            for r in mapping.values()
        )
        and not properties.get(p.removeprefix("wd:"), {}).get("label")
        and not extra.get(p.removeprefix("wd:"), {})
        .get("labels", {})
        .get("en", {})
        .get("value")
    }
    acquired, provenance = acquire_missing(
        unlabeled,
        ROOT / "GG_Data/pipeline/outputs/wikidata_property_cache",
        reference,
        prefix="P",
    )
    extra.update({p: envelope["entity"] for p, envelope in acquired.items()})
    rules = read_csv(NATIVE_RULES)
    evidence = []
    for predicate, cases in sorted(missing.items()):
        prop = predicate.removeprefix("wd:")
        anchors = {
            r["level2_relation_label"]
            for r in mapping.values()
            if r["level2_relation_id"] == predicate
        }
        if len(anchors) > 1:
            raise SourceException("Conflicting existing native labels", **cases[0])
        metadata = properties.get(prop, {})
        entity = extra.get(prop, {})
        label = (
            next(iter(anchors), "")
            or metadata.get("label")
            or entity.get("labels", {}).get("en", {}).get("value")
        )
        if not label:
            raise SourceException("No saved native property label", **cases[0])
        rule = dict.fromkeys(rules[0], "")
        rule.update(
            rule_id=f"native-wikidata-{prop}",
            source="Wikidata",
            source_predicate=predicate,
            normalized_relation_id=predicate,
            relation_label=label,
            relation_description=metadata.get("description", "")
            or entity.get("descriptions", {}).get("en", {}).get("value", ""),
            level2_relation_id=predicate,
            direction_to_level2="same",
            level2_mapping_basis="IDENTICAL_IDENTIFIER",
            source_logic="Approved native preservation; no Level 1 inference. S2T 8.",
            formal_sources="SOURCE_IDENTIFIERS",
            formal_paths=f"{predicate} IDENTICAL {predicate}",
            formal_evidence_urls=f"https://www.wikidata.org/wiki/Property:{prop}",
            statement_ids="|".join(sorted(c["source_record_id"] for c in cases)),
            metadata_snapshot="native_mapping_evidence.json",
            source_occurrence_count=str(len(cases)),
            assertion_review_status="NOT_REVIEWED_NATIVE_IDENTIFIER_PRESERVED",
            assertion_review_notes="Count covers retained D/D sample statements only.",
        )
        rules.append(rule)
        evidence.append(
            dict(
                rule=rule,
                statements=cases,
                saved_metadata=metadata or entity,
                acquired_source=provenance.get(prop),
            )
        )
    directory = output / "mapping"
    directory.mkdir()
    parameters = directory / "NATIVE_RELATION_RULES_v2.1.2.csv"
    write_csv(parameters, rules)
    (directory / "native_mapping_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    version = "relation-map-v2.1.2"
    catalog.build(
        native_rules=parameters,
        version=version,
        output=directory,
        prior_directions=OUT / "RELATION_DIRECTION_CATALOG_v2.1.1.csv",
    )
    rows = read_csv(directory / "RELATION_MAPPING_TABLE_v2.1.2.csv")
    extended = {(r["source"], r["source_predicate"]): r for r in rows}
    if len(extended) != len(rows):
        raise SourceException("Duplicate extended mapping keys")
    # Adding native source keys must not change settled decisions or reverse IDs.
    for key, prior in mapping.items():
        changed = {
            k: [v, extended[key].get(k)]
            for k, v in prior.items()
            if k not in {"relation_map_version", "prior_v2_reverse_policy"}
            and extended[key].get(k) != v
        }
        if changed:
            raise SourceException("Existing mapping changed", key=key, changed=changed)
        if not set(prior["prior_v2_reverse_policy"].split("|")) <= set(
            extended[key]["prior_v2_reverse_policy"].split("|")
        ):
            raise SourceException("Prior policy provenance lost", key=key)
    for predicate in missing:
        rule = extended["Wikidata", predicate]
        if (
            rule["level2_relation_id"] != predicate
            or rule["direction_to_level2"] != "same"
            or rule["level1_family"] != "UNRESOLVED"
            or rule["level1_assignment_status"] != "NOT_ASSIGNED"
        ):
            raise SourceException(
                "Native extension differs from approval", mapping=rule
            )
    return extended, directory, version, evidence


def populate(statements: list[dict], mapping: dict) -> list[dict]:
    """S2T 8/ERD 6: one QID-level base row per native statement.

    Reuse notebook Process 3 stable identity (including original orientation and
    raw dates). Source graph is absent here, not fabricated from provider URL.
    No reverse view or typed-endpoint fan-out is materialized in this table.
    """

    def compact(value: object) -> str:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    result = []
    for case in statements:
        rule = mapping["Wikidata", case["source_predicate"]]
        subject, target = case["subject_qid"], case["object_qid"]
        parts = (
            "Wikidata",
            case["source_record_id"],
            "",
            subject,
            case["source_predicate"],
            target,
            compact(case["raw_time_values"]),
        )
        oid = "obs-" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]
        if rule["direction_to_level2"] == "reverse":
            subject, target = target, subject
        statement = case["raw_statement"]
        reference = compact(
            dict(
                statement_id=case["source_record_id"],
                reference_hashes=[
                    r.get("hash") for r in statement.get("references", [])
                ],
            )
        )
        support = [
            dict(
                source="Wikidata",
                predicate=case["source_predicate"],
                record_id=case["source_record_id"],
                graph="",
                subject_qid=case["subject_qid"],
                object_qid=case["object_qid"],
            )
        ]
        # Keep all 26 legacy fields; unavailable review/classification values
        # are explicit null, never an assertion truth-review claim.
        legacy = dict(
            observation_id=oid,
            subject_qid=subject,
            object_qid=target,
            level1_relation=rule["level1_family"],
            level1_assignment_status=rule["level1_assignment_status"],
            level2_relation=rule["level2_relation_id"],
            level2_label=rule["level2_relation_label"],
            selection_priority="4",
            selection_status="SELECTED",
            direction=rule["direction_to_level2"],
            **{f"time_{k}": case[f"time_{k}"] for k in ("from", "to", "point")},
            time_precision=compact(case["time_precision"]),
            time_status=case["time_status"],
            selected_source="Wikidata",
            selected_source_predicate=case["source_predicate"],
            source_record_id=case["source_record_id"],
            source_graph="",
            source_reference=reference,
            source_support=compact(support),
            evidence_references=compact(
                [
                    dict(
                        reference=reference,
                        record_id=case["source_record_id"],
                        graph="",
                    )
                ]
            ),
            final_review_status=rule.get("final_review_status") or None,
            final_mapping_class=rule.get("final_mapping_class") or None,
            mapping_origin="catalog",
            relation_map_version=rule["relation_map_version"],
        )
        result.append(
            dict(
                **{
                    k: v
                    for k, v in legacy.items()
                    if k not in {"subject_qid", "object_qid"}
                },
                subject_entity_id=subject,
                object_entity_id=target,
                object_value=None,
                input_assertion=dict(
                    legacy_fields=legacy, raw_source=case, mapping=rule
                ),
                sources=case["source_record"],
                count=1,
                embedding=None,
                attributes=dict(
                    rank=statement["rank"],
                    qualifiers=statement.get("qualifiers", {}),
                    time_selection=case["time_selection"],
                ),
            )
        )
    if len({r["observation_id"] for r in result}) != len(result):
        raise SourceException("Repeated base assertion identity")
    return result


def finish_relations(
    retained: list[dict],
    excluded: list[dict],
    counts: Counter,
    mapping: dict,
    output: Path,
    manifest_path: Path,
    reference: dict,
) -> None:
    """Write manifest last, after source/mapping/output preservation checks.

    This D/D-only checkpoint does not include later event links or certify the
    full six-table POC. Audits are supporting files, not extra business tables.
    """
    mapping, directory, version, additions = extend_mapping(
        retained, mapping, output, reference
    )
    relations = populate(retained, mapping)
    lookup_file = (
        directory
        / f"RELATION_DIRECTION_LOOKUP_{version.removeprefix('relation-map-')}.csv"
    )
    lookup = {r["input_relation_id"]: r for r in read_csv(lookup_file)}
    for case, row in zip(retained, relations, strict=True):
        if row["input_assertion"]["raw_source"] != case:
            raise SourceException("Relation source evidence changed", **case)
        rule = mapping["Wikidata", case["source_predicate"]]
        endpoints = [case["subject_qid"], case["object_qid"]]
        if rule["direction_to_level2"] == "reverse":
            endpoints.reverse()
        if [row["subject_entity_id"], row["object_entity_id"]] != endpoints:
            raise SourceException("Relation endpoint orientation differs", **case)
        reverse = lookup[row["level2_relation"]]["output_reverse_relation_id"]
        if lookup[reverse]["output_reverse_relation_id"] != row["level2_relation"]:
            raise SourceException("Reverse lookup is not involutive", **case)
    temporal = [
        dict(
            source_record_id=c["source_record_id"],
            raw_time_values=c["raw_time_values"],
            time_status=c["time_status"],
            time_selection=c["time_selection"],
        )
        for c in retained
        if c["time_status"] == "MULTIPLE"
        or c["time_selection"]["original_pre_1900_end"]
        or any(d["derived"] for d in c["time_selection"]["decisions"].values())
    ]
    for name, rows in (
        ("relations", relations),
        ("excluded_relations", excluded),
        ("temporal_decisions", temporal),
    ):
        path = output / f"{name}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False, allow_nan=False)
        if read_json(path) != rows:
            raise ValueError(f"Written output differs: {path}")
    counts.update(
        native_mapping_keys_added=len(additions),
        temporal_decision_audit_rows=len(temporal),
        output_base_relations=len(relations),
    )
    inputs = [
        Path(__file__),
        NATIVE_RULES,
        PROPERTY_METADATA,
        catalog.ADDITIONAL_METADATA,
        catalog.MAPPING_V2,
        catalog.REVERSE_VALIDATION,
        catalog.ADDITIONAL_REVERSE,
        catalog.INVENTORY,
        OUT / "RELATION_MAPPING_TABLE_v2.1.1.csv",
        OUT / "RELATION_DIRECTION_CATALOG_v2.1.1.csv",
        OUT / "RELATION_DIRECTION_LOOKUP_v2.1.1.csv",
        OUT / "NATIVE_RELATION_EVIDENCE_2026-10-20.json",
        ROOT / "GG_Data/mapping/build_relation_mapping_v2_1.py",
        ROOT / "GG_Data/mapping/rebuild_relation_mapping.py",
        ROOT / "GG_Data/mapping/assertion_exclusions.py",
        ROOT / "GG_Data/pipeline/entities.py",
        ROOT / "GG_Data/entity_resolution/bigquery_direct_wikidata.py",
        ROOT / "GG_Data/mapping/ASSERTION_EXCLUSIONS.csv",
        ROOT / "docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md",
        ROOT / "docs/ENTITY_DATA_MODEL_ERD.md",
    ]
    # The accepted upstream hashes are rechecked after population; no mutation
    # of mentions, entities or historical catalogs is permitted by this step.
    if (
        len(retained) + len(excluded)
        != counts["in_scope_statements_checked"] - counts["repeated_retrievals"]
    ):
        raise ValueError("In-scope assertion accounting differs")
    if digest(manifest_path) != ACCEPTED_ENTITIES_SHA:
        raise ValueError("Accepted Entities manifest changed during Relations")
    upstream = read_json(manifest_path)
    for file, sha in upstream["outputs"].items():
        if digest(manifest_path.parent / file) != sha:
            raise ValueError(f"Accepted Entities source changed: {file}")
    first_manifest = Path(upstream["step1_manifest"]["file"])
    for file, sha in read_json(first_manifest)["outputs"].items():
        if digest(first_manifest.parent / file) != sha:
            raise ValueError(f"Original sample output changed: {file}")
    manifest = dict(
        status="DANIEL_RELATIONS_ONLY",
        scope="Direct assertions between the pinned sample's matched Daniel QIDs only",
        counts=dict(counts),
        time_policy_version=TIME_POLICY,
        relation_map_version=version,
        entities_manifest=dict(file=str(manifest_path), sha256=digest(manifest_path)),
        inputs={str(p.relative_to(ROOT)): digest(p) for p in inputs},
        mapping_artifacts={
            str(p.relative_to(ROOT)): digest(p)
            for p in directory.glob(f"*{version.removeprefix('relation-map-')}*")
            if p.is_file()
        },
        pending_stages=[
            "Events",
            "event links in Relations",
            "Geography",
            "graph",
            "Agent",
        ],
        outputs={
            str(p.relative_to(output)): digest(p)
            for p in output.rglob("*")
            if p.is_file()
        },
        verification="Unique base IDs; source/endpoint preservation; reverse involution; output readback",
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    LOG.info(
        "Daniel-only Relations populated: %d rows; %d native keys added",
        len(relations),
        len(additions),
    )


def run(entities_dir: Path, output: Path) -> None:
    if output.exists() or not output.resolve().is_relative_to(
        ROOT / "GG_Data/pipeline/outputs"
    ):
        raise ValueError("Use a new directory under the approved D: pipeline outputs")
    manifest_path = entities_dir / "manifest.json"
    if digest(manifest_path) != ACCEPTED_ENTITIES_SHA:
        raise ValueError("Accepted Entities manifest differs")
    manifest = read_json(manifest_path)
    if manifest["status"] != "ENTITIES_STEP_ONLY":
        raise ValueError("Expected the accepted Entities step")
    for name, sha in manifest["outputs"].items():
        if digest(entities_dir / name) != sha:
            raise ValueError(f"Entities source hash differs: {name}")
    step1 = manifest["step1_manifest"]
    if digest(Path(step1["file"])) != step1["sha256"]:
        raise ValueError("Original sample manifest differs")
    first = read_json(Path(step1["file"]))
    mentions_path = Path(step1["file"]).parent / "mentions.json.gz"
    if digest(mentions_path) != first["outputs"][mentions_path.name]:
        raise ValueError("Original mentions differ")
    mentions = read_json(mentions_path)
    qids = {
        m["entity_id"]
        for m in mentions
        if re.fullmatch(r"Q[1-9]\d*", m["entity_id"] or "")
    }
    mapping_path = OUT / "RELATION_MAPPING_TABLE_v2.1.1.csv"
    if digest(mapping_path) != BASE_MAPPING_SHA:
        raise ValueError("Approved mapping v2.1.1 differs")
    rows = read_csv(mapping_path)
    mapping = {(r["source"], r["source_predicate"]): r for r in rows}
    if len(rows) != len(mapping):
        raise ValueError("Duplicate mapping keys require consultation")
    cache = Path.home() / ".cache/geoai_full_daniel_dump_bigquery_parallel_20261019"
    if digest(cache / "manifest.json") != first["resolution_run_id"]:
        raise ValueError("Original matching manifest differs")
    saved = read_json(cache / "manifest.json")
    if (
        digest(cache / "reference_manifest.json")
        != saved["outputs"]["reference_manifest.json"]
    ):
        raise ValueError("Pinned BigQuery source reference differs")
    reference = read_json(cache / "reference_manifest.json")
    LOG.info(
        "Read accepted Entities; inspect direct relations for %d Daniel QIDs", len(qids)
    )
    entities = read_entities(entities_dir / "entities.json.gz")
    if len(entities) != manifest["entity_count"] or len(
        {(r["entity_id"], r["type"]) for r in entities}
    ) != len(entities):
        raise ValueError("Entities membership differs")
    output.mkdir(parents=True, exist_ok=False)
    try:
        retained, excluded, counts = scan(entities, qids, mapping)
        LOG.info("Source checks passed: %s", dict(counts))
        finish_relations(
            retained, excluded, counts, mapping, output, manifest_path, reference
        )
    except SourceException as error:
        (output / "first_exception.json").write_text(
            json.dumps(
                dict(
                    status="BLOCKED_RELATIONS_POPULATION",
                    scope="First unexpected case only; no completed Relations output",
                    entities_manifest=dict(
                        file=str(manifest_path), sha256=digest(manifest_path)
                    ),
                    **error.case,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entities",
        type=Path,
        default=ROOT / "GG_Data/pipeline/outputs/poc_10k_entities_approved",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.entities, args.output)


if __name__ == "__main__":
    main()

"""Daniel-QID Relations source check: population S2T 8 and ERD 6.

Read the accepted Entities records only. No network client, entity extraction,
rematching or event discovery is used. Stop at the first unexpected source case.
Event/Daniel links are a later step; this is not a complete Relations release.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import re
from collections import Counter
from pathlib import Path

import ijson

from GG_Data.mapping.assertion_exclusions import exclusion_reason, load_exclusions
from GG_Data.mapping.build_relation_mapping_v2_1 import OUT, read_csv
from GG_Data.pipeline.poc import ROOT, digest, read_json

LOG = logging.getLogger(__name__)
ACCEPTED_ENTITIES_SHA = (
    "a4b967188c7247996309e53dba9851208d8d8e1e69c21d79f7afb1cc35c252e4"
)
BASE_MAPPING_SHA = "8ecdc0095d10ec1fc24dfb82510473faef42b896c126b76cb0daeb233b301821"
TIME_POLICY = "relation-date-selection-v1.0.0"


class SourceException(ValueError):
    """A business/data exception must be shown, not repaired automatically."""

    def __init__(self, reason: str, **case: object):
        self.case = dict(reason=reason, **case)
        super().__init__(f"{reason}: {case.get('source_record_id', '')}")


def statement_time(statement: dict) -> dict:
    """Population S2T 8: approved start/end selection, 20 October 2026.

    Start: earliest supplied value from 1900; all earlier -> derived year 1900.
    End: latest supplied value. Preserve original snaks, precision and calendars.
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

    for name, prop in (("from", "P580"), ("to", "P582"), ("point", "P585")):
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
            if name == "from":
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
                rule="EARLIEST_FROM_1900"
                if name == "from" and candidates
                else "YEAR_1900_FLOOR"
                if name == "from"
                else "LATEST_END",
                derived=name == "from" and not candidates,
                selected_precision=[9]
                if name == "from" and not candidates
                else sorted(
                    {
                        s["datavalue"]["value"]["precision"]
                        for s in snaks
                        if isinstance(s.get("datavalue", {}).get("value"), dict)
                        and s["datavalue"]["value"].get("time") == selected[name]
                        and s["datavalue"]["value"].get("precision") is not None
                    }
                ),
            )
    start, end, point = (selected[k] for k in ("from", "to", "point"))
    first, last = date_parts(start) if start else None, date_parts(end) if end else None
    status = (
        "CONFLICT"
        if first and last and first > last
        else "MULTIPLE"
        if any(len(v) > 1 for v in raw.values())
        else "DIRECT"
        if point or (start and end)
        else "PARTIAL"
        if start or end
        else "NONE"
    )
    return dict(
        time_from=start,
        time_to=end,
        time_point=point,
        time_precision=precisions,
        raw_time_values=raw,
        time_status=status,
        time_selection=dict(policy_version=TIME_POLICY, decisions=decisions),
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
                # User approval, 20 October: a relation ending before 1900 is
                # excluded before the selected-start floor can reverse it.
                if time["time_to"] and int(
                    re.match(r"[+-]\d+", time["time_to"])[0]
                ) < 1900:
                    excluded.append(dict(**case, **time, reason="ENDED_BEFORE_1900"))
                    counts["excluded_ended_before_1900"] += 1
                    continue
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
        # Mapping extension/population is added only after this source check
        # passes; a blocked check is never a completed Relations manifest.
    except SourceException as error:
        (output / "first_exception.json").write_text(
            json.dumps(
                dict(
                    status="BLOCKED_RELATIONS_SOURCE_CHECK",
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
    LOG.info("Source checks passed: %s", dict(counts))
    (output / "source_check.json").write_text(
        json.dumps(
            dict(
                status="DANIEL_RELATIONS_SOURCE_CHECK_ONLY",
                counts=dict(counts),
                time_policy_version=TIME_POLICY,
                entities_manifest=dict(
                    file=str(manifest_path), sha256=digest(manifest_path)
                ),
                mapping=dict(file=str(mapping_path), sha256=digest(mapping_path)),
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    # Implementation resumes here after the strict real-data source gate.


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

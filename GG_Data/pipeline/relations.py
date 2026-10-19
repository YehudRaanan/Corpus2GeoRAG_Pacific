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


class SourceException(ValueError):
    """A business/data exception must be shown, not repaired automatically."""

    def __init__(self, reason: str, **case: object):
        self.case = dict(reason=reason, **case)
        super().__init__(f"{reason}: {case.get('source_record_id', '')}")


def statement_time(statement: dict) -> dict:
    """Reuse notebook Process 3/4: unique qualifier value, never date ranking.

    Preserve every original snak in input_assertion. MULTIPLE/CONFLICT values
    stop this strict POC for consultation, rather than silently selecting one.
    """
    selected, raw, precisions = {}, {}, {}
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
    start, end, point = (selected[k] for k in ("from", "to", "point"))

    def date_parts(value: str) -> tuple[int, ...] | None:
        match = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})", value)
        return tuple(map(int, match.groups())) if match else None

    first, last = date_parts(start), date_parts(end)
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
                time = statement_time(statement)
                if time["time_status"] in {"MULTIPLE", "CONFLICT"}:
                    raise SourceException(
                        "Temporal values require consultation",
                        **case,
                        temporal_evidence=time,
                    )
                rule = mapping.get(("Wikidata", case["source_predicate"]))
                if rule and (
                    rule["direction_to_level2"] not in {"same", "reverse"}
                    or rule["formal_component_conflict"] != "False"
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

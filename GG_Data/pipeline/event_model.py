"""Populate the frozen POC model: population S2T 6-8 and ERD 1/5/6.

Consume verified Event selection and snapshot Entities, without extraction,
rematching or recursive discovery. All unexpected data stop before model writes.
Reuse native assertion validation, mapping, dates and mutual top-20 selection.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from pathlib import Path
from time import perf_counter

import ijson

from GG_Data.mapping.build_relation_mapping_v2_1 import read_csv
from GG_Data.pipeline.entities import choose_name
from GG_Data.pipeline.event_selection import load_scores, select_events
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relation_selection import importance, select
from GG_Data.pipeline.relations import (
    SourceException,
    extend_mapping,
    point_date_range,
    populate,
    read_entities,
    scan,
)

BASE = ROOT / "GG_Data/pipeline/outputs"
SELECTION = BASE / "poc_10k_events_maximum_missing_zero_20261021"
ENTITIES = BASE / "poc_10k_entities_snapshot_first_20261020"
LOG = logging.getLogger(__name__)


def event_rows(record: dict, source: dict, decision: dict) -> tuple[dict, dict]:
    """S2T 6/7: native Event identity, lossless classes/dates, no fake mentions.

    An Event adds its separate event-typed Entity; existing Daniel types stay.
    The approved point-date fallback is explicitly derived, never a source fact.
    Scalar Agent compatibility is a later export check, not a date ranking here.
    """
    qid = record["id"]
    name = choose_name(qid, record, {}, [])  # EN then JA; no Daniel fallback invented.
    claims = record["claims"]
    temporal = {p: claims.get(p, []) for p in ("P580", "P582", "P585")}
    snaks = {
        p: [s["mainsnak"] for s in statements] for p, statements in temporal.items()
    }
    dates = {
        p: [s.get("datavalue", {}).get("value") for s in values]
        for p, values in snaks.items()
    }
    derived = point_date_range(snaks)
    for name_key, prop in (("from", "P580"), ("to", "P582")):
        if name_key in derived:
            dates[prop] = [
                v
                for v in dates["P585"]
                if isinstance(v, dict) and v.get("time") == derived[name_key]["value"]
            ]
    details = [
        dict(
            label=value["value"],
            kind="label",
            provider="WIKIDATA",
            record_id=qid,
            language=language,
        )
        for language, value in record.get("labels", {}).items()
    ] + [
        dict(
            label=value["value"],
            kind="alias",
            provider="WIKIDATA",
            record_id=qid,
            language=language,
        )
        for language, values in record.get("aliases", {}).items()
        for value in values
    ]
    entity = dict(
        entity_id=qid,
        type="event",
        name=name["value"],
        labels=record.get("labels", {}),
        descriptions=record.get("descriptions", {}),
        aliases=sorted({d["label"] for d in details}),
        alias_details=details,
        identity_status="QID_MATCHED",
        review_status="NOT_REVIEWED",
        sources=[source],
        text=None,
        embedding=None,
        importance=None,
        attributes=dict(name_selection=name, mention_ids=[], event_selection=decision),
        direct_types=[
            s.get("mainsnak", {}).get("datavalue", {}).get("value")
            for s in claims.get("P31", [])
        ],
        parents=[
            s.get("mainsnak", {}).get("datavalue", {}).get("value")
            for s in claims.get("P279", [])
        ],
        sitelinks=record.get("sitelinks", {}),
        revision=record.get("lastrevid"),
        modified=record.get("modified"),
        missing=False,
        reference_source="BIGQUERY",
        raw_reference=dict(full=dict(requested_qid=qid, entity=record), matching={}),
    )
    event = dict(
        event_id=qid,
        kind=entity["direct_types"],
        start_date=dates["P580"],
        end_date=dates["P582"],
        point_date=dates["P585"],
        temporal_evidence=dict(claims=temporal, derived_range=derived),
        event_map_version=None,
        importance=None,
        attributes=dict(
            classification_claims=claims.get("P31", []), selection=decision
        ),
    )
    return entity, event


def run(output: Path) -> dict:
    started = perf_counter()
    if output.exists() or not output.resolve().is_relative_to(BASE):
        raise ValueError("Use a new directory under approved pipeline outputs")
    output.mkdir(parents=True)
    report = dict(
        status="VALIDATING_INPUTS",
        model_rows_written=0,
        final_graph_written=False,
        new_source_requests=0,
        inputs={},
    )

    def save() -> None:
        report["elapsed_seconds"] = perf_counter() - started
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    def pin(path: Path) -> str:
        value = digest(path)
        report["inputs"][str(path)] = value
        return value

    save()
    try:
        receipt = read_json(SELECTION / "report.json")
        if (
            read_json(SELECTION / "verification.json")["report_sha256"]
            != pin(SELECTION / "report.json")
            or not receipt["full_retained_scope_checked"]
            or receipt["event_relevance_aggregation"] != "maximum_missing_zero"
        ):
            raise SourceException("Expected verified maximum Event selection")
        for name, expected in receipt["outputs"].items():
            if pin(SELECTION / name) != expected:
                raise SourceException("Event input checksum differs", file=name)
        manifest = read_json(ENTITIES / "manifest.json")
        if (
            read_json(ENTITIES / "verification.json")["manifest_sha256"]
            != pin(ENTITIES / "manifest.json")
            or manifest["snapshot_at"] != receipt["snapshot_at"]
        ):
            raise SourceException("Entities snapshot verification differs")
        for name, expected in manifest["outputs"].items():
            if pin(ENTITIES / name) != expected:
                raise SourceException("Entities checksum differs", file=name)
        pin(Path(__file__))
        for name in (
            "relations.py",
            "relation_selection.py",
            "entities.py",
            "event_selection.py",
        ):
            pin(ROOT / "GG_Data/pipeline" / name)
        pin(ROOT / "GG_Data/mapping/ASSERTION_EXCLUSIONS.csv")
        pin(ROOT / "docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md")
        decisions = read_json(SELECTION / "decisions.json")
        retained = set(read_json(SELECTION / "retrieval_scope.json")["retained_qids"])
        # These saved candidates already passed native Event recognition in
        # event_population.run; replay selection, not hierarchy discovery.
        replay = select_events(
            [
                dict(
                    qid=r["qid"],
                    event_hierarchy_match=True,
                    daniel_qids=r["linked_entity_qids"],
                )
                for r in decisions
            ],
            retained,
            load_scores(retained),
        )
        if any(
            a["keep_event"] != b["keep_event"]
            for a, b in zip(decisions, replay, strict=True)
        ):
            raise SourceException("Event decision replay differs")
        chosen = {r["qid"]: r for r in decisions if r["keep_event"]}
        if set(chosen) != set(receipt["included_event_qids"]):
            raise SourceException("Selected Event population differs")
        report.update(included_events=len(chosen), snapshot_at=receipt["snapshot_at"])
        save()
        original = read_entities(ENTITIES / "entities.json.gz")
        daniel = {r["entity_id"] for r in original if r["entity_id"].startswith("Q")}
        existing = {(r["entity_id"], r["type"]) for r in original}
        raw_events = {}
        with gzip.open(SELECTION / "full_records.json.gz", "rb") as stream:
            for qid, record in ijson.kvitems(stream, "", use_float=True):
                if qid in chosen:
                    raw_events[qid] = record
        if set(raw_events) != set(chosen):
            raise SourceException("Selected native Event records incomplete")
        additions, event_table = [], []
        for qid, record in sorted(raw_events.items()):
            if (qid, "event") in existing:
                raise SourceException("Event typed row already exists", qid=qid)
            source = dict(
                provider="BIGQUERY",
                file=str(SELECTION / "full_records.json.gz"),
                sha256=receipt["outputs"]["full_records.json.gz"],
                record_id=qid,
                snapshot_at=receipt["snapshot_at"],
                revision=record.get("lastrevid"),
            )
            entity, event = event_rows(record, source, chosen[qid])
            additions.append(entity)
            event_table.append(event)
        mapping = {
            (r["source"], r["source_predicate"]): r
            for r in read_csv(SELECTION / "mapping/RELATION_MAPPING_TABLE_v2.1.2.csv")
        }
        report["status"] = "VALIDATING_ALL_NATIVE_RELATIONS"
        save()
        # S2T 8: all original Daniel QIDs plus independently selected Events.
        # This includes Event/Event links, without expanding discovery or capping them.
        statements, excluded, counts = scan(
            original + additions, daniel | set(chosen), mapping
        )
        report["source_scan_counts"] = dict(counts)
        missing = {
            r["source_predicate"]
            for r in statements
            if ("Wikidata", r["source_predicate"]) not in mapping
        }
        if missing:
            # Existing approved native-property extension, not a new semantic rule.
            refs = [
                Path(p)
                for p in manifest["inputs"]
                if Path(p).name == "reference_manifest.json"
            ]
            if len(refs) != 1:
                raise SourceException("Expected one pinned reference manifest")
            reference = read_json(refs[0])
            report["new_source_requests"] = (
                None  # Metadata cache/query use is recorded by extension.
            )
            mapping, _, _, _ = extend_mapping(
                statements,
                mapping,
                output,
                reference,
                native_rules=SELECTION / "mapping/NATIVE_RELATION_RULES_v2.1.2.csv",
            )
        relations = populate(statements, mapping)
        temporal = [
            dict(
                source_record_id=c["source_record_id"],
                raw_time_values=c["raw_time_values"],
                time_status=c["time_status"],
                time_selection=c["time_selection"],
            )
            for c in statements
            if c["time_status"] == "MULTIPLE"
            or c["time_selection"]["original_pre_1900_end"]
            or any(d["derived"] for d in c["time_selection"]["decisions"].values())
        ]
        mentions = BASE / "poc_10k/mentions.json.gz"
        first = read_json(mentions.parent / "manifest.json")
        if pin(mentions) != first["outputs"][mentions.name]:
            raise SourceException("Original 10K Mentions changed")
        scores = importance(read_json(mentions))
        # Complete membership is established above; the existing cap keeps Event links exempt.
        relations, audit = select(
            relations, scores, set(chosen), event_population_complete=True
        )
        model_entities = original + additions
        keys = {(r["entity_id"], r["type"]) for r in model_entities}
        if len(keys) != len(model_entities) or not existing <= keys:
            raise SourceException("Typed Entity identity preservation failed")
        entity_qids = {r["entity_id"] for r in model_entities}
        if any(
            not {r["subject_entity_id"], r["object_entity_id"]} <= entity_qids
            for r in relations
        ):
            raise SourceException("Relation endpoint missing in Entities")
        for path, expected in report["inputs"].items():
            if digest(Path(path)) != expected:
                raise SourceException("Input changed during population", file=path)
        # Write only after every data/business gate passes. Prior artifacts stay immutable.
        for name, rows in (
            ("entities", model_entities),
            ("events", event_table),
            ("relations", relations),
            ("relation_selection", audit),
            ("temporal_decisions", temporal),
            ("excluded_relations", excluded),
        ):
            path = output / f"{name}.json.gz"
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                json.dump(rows, stream, ensure_ascii=False, allow_nan=False)
            if read_json(path) != rows:
                raise SourceException("Model output readback differs", file=str(path))
            if name in {"entities", "events", "relations"}:
                report["model_rows_written"] += len(rows)
        report.update(
            status="EVENTS_AND_RELATIONS_POPULATED",
            entity_rows=len(model_entities),
            event_rows=len(event_table),
            relation_rows=len(relations),
            model_rows_written=len(model_entities) + len(event_table) + len(relations),
            original_entity_rows=len(original),
            pending_stages=["Geography", "graph export", "Agent integration"],
            outputs={p.name: digest(p) for p in output.glob("*.json.gz")},
        )
        save()
        (output / "manifest.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (output / "verification.json").write_text(
            json.dumps(
                dict(
                    status="VERIFIED_EVENTS_AND_RELATIONS_MODEL",
                    report_sha256=digest(output / "report.json"),
                    original_entities_preserved=True,
                    native_event_ids_preserved=True,
                    native_relation_validation=True,
                    output_readback=True,
                    final_graph_written=False,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        report.update(
            status="STOPPED_FOR_CONSULTATION",
            error=f"{type(exc).__name__}: {exc}",
            exception=getattr(exc, "case", None),
        )
        save()
        raise
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(parser.parse_args().output)
    LOG.info("%s in %.3fs", result["status"], result["elapsed_seconds"])

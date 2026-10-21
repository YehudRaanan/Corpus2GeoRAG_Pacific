"""Full retained-Daniel Event check; population S2T 6.1/7/8.

Run source filtering in BigQuery, reuse frozen native Daniel assertions and the
accepted occurrence hierarchy. Never expand Daniel's population or invent links.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import re
import sys
from pathlib import Path
from time import perf_counter

from GG_Data.mapping.build_relation_mapping_v2_1 import read_csv
from GG_Data.pipeline import events
from GG_Data.pipeline.event_candidate_check import qualifying_links, statement_key
from GG_Data.pipeline.event_selection import (
    BASE,
    MINIMUM_DANIEL_QIDS,
    prepare,
    select_events,
)
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException, extend_mapping

LOG = logging.getLogger(__name__)
HIERARCHY = BASE / "event_hierarchy_bigquery_occurrence_test_20261021"
ENTITIES = BASE / "poc_10k_entities_snapshot_first_20261020"
RELATIONS = BASE / "poc_10k_relations_original_historical_dates_20261020"
STORE = BASE / "wikidata_event_snapshot_discovery_cache"


def discovery_query(
    source: str, daniel: set[str], types_table: str, pairs_table: str
) -> str:
    """S2T 7: both native directions, distinct QIDs, then native recognition.

    A cached Daniel -> Event pair survives even with no Event -> Daniel link.
    Full records are returned only after the preliminary three-QID gate and
    recognition. Local exclusions/mapping must still precede final inclusion.
    Uploaded tables contain class IDs and endpoint pairs, never inferred edges.
    """
    if not daniel or any(not re.fullmatch(r"Q[1-9]\d*", q) for q in daniel):
        raise ValueError("Expected retained native Daniel QIDs")
    if any(not re.fullmatch(r"[a-z0-9_.-]+", t) for t in (types_table, pairs_table)):
        raise ValueError("Unexpected cloud parameter table")
    targets = ",".join(f"'{q}'" for q in sorted(daniel))
    return f"""WITH outgoing AS (
 SELECT JSON_VALUE(pair, '$.event_qid') AS event_qid,
   ARRAY_AGG(DISTINCT JSON_VALUE(pair, '$.daniel_qid')) AS daniel_qids
 FROM `{pairs_table}` GROUP BY event_qid
), parsed AS (
 SELECT id, item,
   PARSE_JSON(RTRIM(item, ',\\n\\r '), wide_number_mode=>'round')['claims'] AS claims
 FROM {source} WHERE STARTS_WITH(id, 'Q')
), recognized AS (
 SELECT r.* FROM parsed r,
   UNNEST(JSON_QUERY_ARRAY(claims['P31'])) AS s
 JOIN `{types_table}` t
   ON JSON_VALUE(s, '$.mainsnak.datavalue.value.id')=t.event_type
 WHERE JSON_VALUE(s, '$.rank') IN ('normal', 'preferred')
 QUALIFY ROW_NUMBER() OVER (PARTITION BY id)=1
), connected AS (
 SELECT r.*, ARRAY(
   SELECT DISTINCT q FROM UNNEST(ARRAY_CONCAT(
     IFNULL(o.daniel_qids, ARRAY<STRING>[]),
     ARRAY(SELECT DISTINCT JSON_VALUE(s, '$.mainsnak.datavalue.value.id')
       FROM UNNEST(JSON_KEYS(claims, 1)) AS p,
            UNNEST(JSON_QUERY_ARRAY(claims[p])) AS s
       WHERE JSON_VALUE(s, '$.mainsnak.datavalue.value.entity-type') = 'item'
         AND JSON_VALUE(s, '$.mainsnak.datavalue.value.id') IN ({targets}))
   )) AS q ORDER BY q
 ) AS daniel_qids
 FROM recognized r LEFT JOIN outgoing o ON o.event_qid=r.id
)
SELECT id AS qid, item, daniel_qids
FROM connected
WHERE ARRAY_LENGTH(daniel_qids) >= {MINIMUM_DANIEL_QIDS}
ORDER BY qid"""


def native_item(raw: str) -> dict:
    return json.loads(raw.rstrip(",\n\r "))


def verify_recognition(record: dict, types: set[str]) -> bool:
    """Replay cloud recognition from full native P31, not a name or category."""
    return any(
        s.get("rank") in {"normal", "preferred"}
        and s.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
        in types
        for s in record.get("claims", {}).get("P31", [])
    )


def run(output: Path) -> dict:
    started = perf_counter()
    scope = prepare(output)
    report = dict(
        status="PREPARING_CLOUD_EVENT_CHECK",
        event_rows_written=0,
        final_graph_written=False,
        full_retained_scope_checked=False,
        minimum_distinct_daniel_qids=MINIMUM_DANIEL_QIDS,
        event_threshold_percent=None,
        scope_counts={
            k: len(v) if isinstance(v, list) else v for k, v in scope.items()
        },
        inputs={},
        source_requests=[],
    )

    def write(name: str, value: object) -> None:
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def save() -> None:
        report["elapsed_seconds"] = perf_counter() - started
        write("report.json", report)

    save()
    try:
        approval = read_json(HIERARCHY / "recognition_approval.json")
        if (
            approval["status"] != "RECOGNITION_RULE_ACCEPTED"
            or approval["root_qid"] != "Q1190554"
        ):
            raise ValueError("Expected accepted native occurrence hierarchy")
        type_path = HIERARCHY / "parameters/event_types.csv"
        # The approval binds the complete saved class list, not a manual subset.
        expected = approval["parameter_hashes"]
        hashes = {str(k).split("/")[-1]: v for k, v in expected.items()}
        if digest(type_path) != hashes.get("event_types.csv"):
            raise ValueError("Accepted Event type parameters changed")
        with type_path.open(encoding="utf-8-sig", newline="") as stream:
            types = {r["subtype_qid"] for r in csv.DictReader(stream)}
        if not types or any(not re.fullmatch(r"Q[1-9]\d*", q) for q in types):
            raise ValueError("Invalid Event class parameters")
        daniel = set(scope["retained_qids"])
        records = read_json(ENTITIES / "full_records.json.gz")
        all_outgoing = [
            link
            for q in sorted(daniel)
            for link in events.item_links(records[q]["entity"])
        ]
        by_event = {}
        for link in all_outgoing:
            by_event.setdefault(link["object_qid"], []).append(link)
        pairs = [
            json.dumps(dict(event_qid=q, daniel_qid=d), sort_keys=True)
            for q in sorted(by_event)
            for d in sorted({r["subject_qid"] for r in by_event[q]})
        ]
        manifest = read_json(ENTITIES / "manifest.json")
        references = [
            Path(p)
            for p in manifest["inputs"]
            if Path(p).name == "reference_manifest.json"
        ]
        if (
            len(references) != 1
            or digest(references[0]) != manifest["inputs"][str(references[0])]
        ):
            raise ValueError("Frozen reference manifest changed")
        ref = read_json(references[0])
        if read_json(STORE / "table_snapshot.json") != ref["table_snapshot"]:
            raise ValueError("Cloud cache uses another snapshot")
        mapping_path = RELATIONS / "mapping/RELATION_MAPPING_TABLE_v2.1.2.csv"
        mapping_manifest = read_json(RELATIONS / "manifest.json")
        if (
            digest(mapping_path)
            != mapping_manifest["mapping_artifacts"][
                str(mapping_path.relative_to(ROOT))
            ]
        ):
            raise ValueError("Accepted mapping changed")
        mapping_rows = read_csv(mapping_path)
        mapping = {(r["source"], r["source_predicate"]): r for r in mapping_rows}
        if len(mapping) != len(mapping_rows):
            raise ValueError("Duplicate mapping keys")
        paths = [
            type_path,
            HIERARCHY / "recognition_approval.json",
            mapping_path,
            ENTITIES / "manifest.json",
            references[0],
            Path(__file__),
            ROOT / "GG_Data/pipeline/event_selection.py",
            ROOT / "GG_Data/mapping/ASSERTION_EXCLUSIONS.csv",
        ]
        report["inputs"] = {str(p): digest(p) for p in paths}
        report.update(
            event_class_count=len(types),
            outgoing_distinct_pairs=len(pairs),
            outgoing_native_assertions=len(all_outgoing),
            snapshot_at=ref["table_snapshot"]["snapshot_at"],
        )
        write("outgoing_pairs.json", [json.loads(p) for p in pairs])
        save()
        sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
        try:
            from bigquery_direct_wikidata import BigQueryData
        finally:
            sys.path.pop(0)
        client = BigQueryData(ref["project"], STORE)
        types_table = client.upload_values(sorted(types), "event_type")
        pairs_table = client.upload_values(pairs, "pair")
        report["parameter_tables"] = dict(types=types_table, outgoing=pairs_table)
        sql = discovery_query(client.source, daniel, types_table, pairs_table)
        (output / "query.sql").write_text(sql, encoding="utf-8")
        report["status"] = "QUERYING_FULL_RETAINED_SCOPE_IN_BIGQUERY"
        save()
        answer = client.query(sql)
        report["source_requests"] = client.requests
        with gzip.open(
            output / "query_result.json.gz", "wt", encoding="utf-8"
        ) as stream:
            json.dump(answer, stream, ensure_ascii=False)
        report.update(
            status="VALIDATING_NATIVE_EVENT_LINKS", cloud_preliminary_events=len(answer)
        )
        save()
        native, candidate_links = {}, {}
        for row in answer:
            qid, record = row["qid"], native_item(row["item"])
            if (
                qid in native
                or record["id"] != qid
                or not verify_recognition(record, types)
            ):
                raise SourceException(
                    "Cloud Event identity/recognition differs", qid=qid
                )
            native[qid] = record
            links = events.item_links(record) + by_event.get(qid, [])
            endpoints = {
                r["object_qid"] if r["subject_qid"] == qid else r["subject_qid"]
                for r in links
                if qid in {r["subject_qid"], r["object_qid"]}
            }
            if sorted(endpoints & daniel) != row["daniel_qids"]:
                raise SourceException(
                    "Cloud/local distinct endpoint counts differ", qid=qid
                )
            candidate_links[qid] = links
        # S2T 8: use the existing approved native-property extension mechanism.
        relevant = [
            r
            for q, links in candidate_links.items()
            for r in links
            if (r["object_qid"] if r["subject_qid"] == q else r["subject_qid"])
            in daniel
        ]
        mapping, _, _, additions = extend_mapping(
            relevant,
            mapping,
            output,
            ref,
            native_rules=RELATIONS / "mapping/NATIVE_RELATION_RULES_v2.1.2.csv",
        )
        decisions = []
        for qid, links in candidate_links.items():
            kept, excluded = qualifying_links(links, qid, daniel, mapping)
            endpoints = sorted({r["daniel_qid"] for r in kept})
            decision = select_events(
                [dict(qid=qid, event_hierarchy_match=True, daniel_qids=endpoints)],
                daniel,
            )[0]
            decisions.append(dict(decision, links=kept, excluded=excluded))
        write("decisions.json", decisions)
        with gzip.open(
            output / "full_records.json.gz", "wt", encoding="utf-8"
        ) as stream:
            json.dump(native, stream, ensure_ascii=False)
        selected = [r for r in decisions if r["keep_event"]]
        # Preserve one native assertion identity across Event endpoints/retrievals.
        unique = {}
        for decision in selected:
            for link in decision["links"]:
                key = statement_key(link["source_record_id"])
                prior = unique.setdefault(key, link)
                if any(
                    prior[k] != link[k]
                    for k in (
                        "subject_qid",
                        "object_qid",
                        "source_predicate",
                        "raw_statement",
                    )
                ):
                    raise SourceException(
                        "Conflicting retained assertion", statement=key
                    )
        write("selected_links.json", list(unique.values()))
        report.update(
            status="FULL_RETAINED_SCOPE_EVENT_CHECK_COMPLETE",
            full_retained_scope_checked=True,
            included_event_qids=[r["qid"] for r in selected],
            included_events=len(selected),
            rejected_after_exclusions=len(decisions) - len(selected),
            native_event_daniel_assertions=len(unique),
            native_mapping_keys_added=len(additions),
            event_model_population_pending=True,
        )
        for p, sha in report["inputs"].items():
            if digest(Path(p)) != sha:
                raise ValueError(f"Input changed during Event check: {p}")
        report["outputs"] = {
            str(p.relative_to(output)): digest(p)
            for p in output.rglob("*")
            if p.is_file() and p.name != "report.json"
        }
        save()
        write(
            "verification.json",
            dict(
                status="VERIFIED_FULL_RETAINED_SCOPE_EVENT_CHECK",
                report_sha256=digest(output / "report.json"),
                both_directions_checked=True,
                native_recognition_replayed=True,
                distinct_counts_replayed=True,
                source_rows_complete=True,
                event_rows_written=0,
                final_graph_written=False,
            ),
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(args.output)
    LOG.info(
        "%s: %s included Events in %.3f seconds",
        result["status"],
        result["included_events"],
        result["elapsed_seconds"],
    )

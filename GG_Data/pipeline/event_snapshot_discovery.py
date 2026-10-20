"""Event acquisition preflight: population S2T 1/7, hierarchy exception.

Keep snapshot assertions separate from the approved latest-available hierarchy.
This step measures the incoming candidate population before downloading records;
it never writes model Events, new Daniel entities, or selected Relations.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.poc import ROOT, digest, read_json


def measure_query(source: str, daniel: set[str], outgoing: set[str]) -> str:
    """Measure a superset of the existing two-distinct-Daniel-QID gate.

    All native main-item statements/ranks remain eligible. Two incoming Daniel
    targets suffice for this preliminary pool. One incoming target also remains
    eligible when Daniel has an outgoing link to the candidate. Candidates with
    only Daniel -> candidate links are already in the local outgoing inventory.
    Mapping/exclusions, distinct union counts and hierarchy still apply later.
    JSON parsing here selects records only; untouched item JSON stays upstream.
    """
    if not daniel or any(not re.fullmatch(r"Q[1-9]\d*", q) for q in daniel | outgoing):
        raise ValueError("Expected distinct native reference QIDs")
    targets = ",".join(f"'{q}'" for q in sorted(daniel))
    numbers = ",".join(q[1:] for q in sorted(outgoing)) or "NULL"
    return f"""WITH parsed AS (
 SELECT id, numeric_id, BYTE_LENGTH(item) AS item_bytes,
   PARSE_JSON(RTRIM(item, ',\\n\\r '), wide_number_mode=>'round')['claims'] AS claims
 FROM {source} WHERE STARTS_WITH(id, 'Q')
), linked AS (
 SELECT id, numeric_id, item_bytes,
   ARRAY(SELECT DISTINCT JSON_VALUE(s, '$.mainsnak.datavalue.value.id')
     FROM UNNEST(JSON_KEYS(claims, 1)) AS p,
          UNNEST(JSON_QUERY_ARRAY(claims[p])) AS s
     WHERE JSON_VALUE(s, '$.mainsnak.datavalue.value.entity-type') = 'item'
       AND JSON_VALUE(s, '$.mainsnak.datavalue.value.id') IN ({targets})
   ) AS targets
 FROM parsed
), candidates AS (
 SELECT * FROM linked
 WHERE ARRAY_LENGTH(targets) >= 2
    OR (ARRAY_LENGTH(targets) = 1 AND numeric_id IN ({numbers}))
)
SELECT COUNT(*) AS incoming_candidate_count,
       COALESCE(SUM(item_bytes), 0) AS full_record_bytes,
       COUNTIF(ARRAY_LENGTH(targets) = 1) AS single_incoming_with_outgoing,
       COUNTIF(ARRAY_LENGTH(targets) >= 2) AS multiple_incoming
FROM candidates"""


def run(
    entities: Path,
    mentions: Path,
    hierarchy: Path,
    reference: Path,
    store: Path,
    output: Path,
) -> dict:
    """Verify saved inputs; use the existing dry-run/billing/cache CLI adapter."""
    if output.exists() or any(
        not p.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs")
        for p in (output, store)
    ):
        raise ValueError("Use a new approved pipeline output directory")
    accepted = read_json(entities / "verification.json")
    manifest = read_json(entities / "manifest.json")
    if (
        accepted["status"] != "VERIFIED_ENTITIES_SNAPSHOT_FIRST"
        or digest(entities / "manifest.json") != accepted["manifest_sha256"]
    ):
        raise ValueError("Expected verified snapshot-first Entities")
    for name, sha in manifest["outputs"].items():
        if digest(entities / name) != sha:
            raise ValueError(f"Entity output changed: {name}")
    first = read_json(mentions.parent / "manifest.json")
    if digest(mentions) != first["outputs"][mentions.name]:
        raise ValueError("Frozen Mentions changed")
    ref = read_json(reference)
    if (
        manifest["inputs"].get(str(reference)) != digest(reference)
        or ref["table_snapshot"]["snapshot_at"] != manifest["snapshot_at"]
    ):
        raise ValueError("Reference snapshot differs")
    check = read_json(hierarchy / "verification.json")
    for name, sha in check["outputs"].items():
        if digest(hierarchy / name) != sha:
            raise ValueError(f"Hierarchy evidence changed: {name}")
    probe = read_json(hierarchy / "probe.json")
    for row in probe["queries"]:
        evidence = row["source"]
        if digest(Path(evidence["cache"]) / "response.json") != evidence["sha256"]:
            raise ValueError("Hierarchy source response changed")
    # Latest user approval: use cached current P31/P279 for classification only.
    # Never replace snapshot assertion records with these hierarchy statements.
    classified = events.classify_events(read_json(hierarchy / "hierarchy_edges.json"))
    daniel = {
        row["entity_id"]
        for row in read_json(mentions)
        if row["raw"]["entity_group"] != "DATE"
        and re.fullmatch(r"Q[1-9]\d*", row.get("entity_id") or "")
    }
    records = read_json(entities / "full_records.json.gz")
    if set(records) != daniel:
        raise ValueError("Native records differ from frozen Daniel population")
    outgoing = {
        link["object_qid"]
        for envelope in records.values()
        for link in events.item_links(envelope["entity"])
    }
    store.mkdir(parents=True, exist_ok=True)
    snapshot_file = store / "table_snapshot.json"
    if snapshot_file.exists() and read_json(snapshot_file) != ref["table_snapshot"]:
        raise ValueError("Discovery cache snapshot differs")
    if not snapshot_file.exists():
        snapshot_file.write_text(json.dumps(ref["table_snapshot"]), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from bigquery_direct_wikidata import BigQueryData
    finally:
        sys.path.pop(0)
    client = BigQueryData(ref["project"], store)
    output.mkdir(parents=True)
    report = dict(
        status="MEASURING_SNAPSHOT_CANDIDATES",
        snapshot_at=manifest["snapshot_at"],
        hierarchy_policy="LATEST_AVAILABLE_CACHED_WIKIDATA_P31_P279_NONDEPRECATED",
        root=events.EVENT_ROOT,
        cached_classified_candidates=len(classified),
        cached_hierarchy_positive=[
            r["qid"] for r in classified if r["event_hierarchy_match"]
        ],
        daniel_qids=len(daniel),
        outgoing_reference_qids=len(outgoing),
        events_complete=False,
        event_rows_written=0,
        final_graph_written=False,
        inputs={
            str(p): digest(p)
            for p in (
                entities / "manifest.json",
                entities / "full_records.json.gz",
                mentions,
                reference,
                hierarchy / "hierarchy_edges.json",
                hierarchy / "verification.json",
            )
        },
        code_sha256=digest(Path(__file__)),
    )
    (output / "classifications.json").write_text(
        json.dumps(classified, indent=2), encoding="utf-8"
    )
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    try:
        sql = measure_query(client.source, daniel, outgoing)
        result = client.query(sql)
        if len(result) != 1 or any(
            int(result[0][k]) < 0
            for k in (
                "incoming_candidate_count",
                "full_record_bytes",
                "single_incoming_with_outgoing",
                "multiple_incoming",
            )
        ):
            raise ValueError("Unexpected candidate measurement result")
        report.update(
            status="SNAPSHOT_CANDIDATES_MEASURED_ONLY",
            measurement=result[0],
            request=client.requests[-1],
        )
    except (RuntimeError, ValueError) as exc:
        # The POC stops on the first unapproved source/data failure. No retry,
        # snapshot substitution, size cap, relevance filter or Event is inferred.
        report.update(status="BLOCKED_SNAPSHOT_CANDIDATE_MEASUREMENT", error=str(exc))
    report["outputs"] = {
        "classifications.json": digest(output / "classifications.json")
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("entities", "mentions", "hierarchy", "reference", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(
        args.entities,
        args.mentions,
        args.hierarchy,
        args.reference,
        args.store,
        args.output,
    )
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"inputs", "request"}})
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

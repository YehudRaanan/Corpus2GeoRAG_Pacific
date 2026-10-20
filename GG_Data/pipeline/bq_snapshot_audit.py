"""Mark saved BQ coverage, without retrieval or rematching (population S2T 1).

The 20 October alignment decision supersedes live Event fallback. Presence in
compact matching metadata does not certify complete full-record/edge coverage.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

import ijson

from GG_Data.pipeline.entities import digest_sql
from GG_Data.pipeline.poc import ROOT, digest, read_json

TABLE = "bigquery-public-data.wikipedia.wikidata"
ROOT_QID = "Q140451665"


def availability(qid: str, metadata: dict | None) -> str:
    """Only an explicit saved BQ missing marker establishes a known miss."""
    if qid.startswith("SYN_"):
        return "NOT_APPLICABLE_SYNTHETIC"
    if metadata is None:
        return "NOT_CHECKED"
    if (
        metadata.get("id") != qid
        or metadata.get("reference_source") != "BIGQUERY"
        or type(metadata.get("missing")) is not bool
    ):
        raise ValueError(f"Unverified BigQuery availability evidence: {qid}")
    return "MISSING_IN_PINNED_BQ" if metadata["missing"] else "PRESENT_IN_PINNED_BQ"


def run(cache: Path, entities: Path, output: Path) -> dict:
    """Reuse verified artifacts; keep all existing model fields and old outputs."""
    if output.exists() or not output.resolve().is_relative_to(
        ROOT / "GG_Data/pipeline/outputs"
    ):
        raise ValueError("Use a new approved pipeline output directory")
    matching = read_json(cache / "manifest.json")
    reference = read_json(cache / "reference_manifest.json")
    snapshot = reference["table_snapshot"]
    for name in ("reference_manifest.json", "entity_metadata.json.gz"):
        if digest(cache / name) != matching["outputs"][name]:
            raise ValueError(f"Matching evidence hash differs: {name}")
    step1 = read_json(ROOT / "GG_Data/pipeline/outputs/poc_10k/manifest.json")
    if digest(cache / "manifest.json") != step1["resolution_run_id"]:
        raise ValueError("Expected the original matching snapshot")
    manifest = read_json(entities / "manifest.json")
    check = read_json(entities / "verification.json")
    if (
        check["status"] != "VERIFIED_ENTITIES_IMPORTANCE_INCLUDING_SYNTHETICS"
        or digest(entities / "manifest.json") != check["manifest_sha256"]
    ):
        raise ValueError("Expected verified scored Entities")
    for name, sha in manifest["outputs"].items():
        if digest(entities / name) != sha:
            raise ValueError(f"Entities input hash differs: {name}")
    rows = read_json(entities / "entities.json.gz")
    qids = {r["entity_id"] for r in rows if r["entity_id"].startswith("Q")}
    selected, missing = {}, []
    with gzip.open(cache / "entity_metadata.json.gz", "rb") as stream:
        for qid, record in ijson.kvitems(stream, "", use_float=True):
            if qid in qids:
                selected[qid] = record
            if record.get("missing") is True:
                missing.append(
                    dict(
                        entity_id=qid,
                        status=availability(qid, record),
                        scope="SAVED_MATCHING_REFERENCE_LOOKUPS",
                        in_poc_entities=qid in qids,
                    )
                )
    if qids - selected.keys():
        raise ValueError("POC QID availability has not been checked")
    # Reuse the exact zero-row root query, not absence from a local directory.
    store = ROOT / "GG_Data/pipeline/outputs/wikidata_event_cache"
    if read_json(store / "table_snapshot.json") != snapshot:
        raise ValueError("Event-root cache snapshot differs from matching")
    sql = (
        f"SELECT id, item FROM `{TABLE}` AS w FOR SYSTEM_TIME AS OF TIMESTAMP "
        f"'{snapshot['snapshot_at']}' WHERE numeric_id IN (140451665) "
        "AND STARTS_WITH(id,'Q')"
    )
    key = digest_sql(sql)
    if (store / f"{key}.sql").read_text(encoding="utf-8") != sql:
        raise ValueError("Event-root query scope differs")
    root_result = read_json(store / f"{key}.json.gz")
    if root_result["sql_sha256"] != key or root_result["rows"] != []:
        raise ValueError("Expected the known empty Event-root result")
    missing.append(
        dict(
            entity_id=ROOT_QID,
            status="MISSING_IN_PINNED_BQ",
            scope="EVENT_CLASSIFICATION_ROOT",
            in_poc_entities=ROOT_QID in qids,
            job_id=root_result["job_id"],
        )
    )
    for row in rows:
        qid = row["entity_id"]
        row["attributes"]["bq_availability"] = dict(
            status=availability(qid, selected.get(qid)),
            table=TABLE,
            snapshot_at=snapshot["snapshot_at"],
            evidence="SAVED_MATCHING_METADATA",
            full_record_alignment_verified=False,
        )
    # Missing reference QIDs remain audit entries, never new Entity rows.
    output.mkdir(parents=True)
    for name, values in (("entities", rows), ("bq_missing_analysis", missing)):
        with gzip.open(output / f"{name}.json.gz", "wt", encoding="utf-8") as f:
            json.dump(values, f, ensure_ascii=False, allow_nan=False)
    result = dict(
        status="BQ_COVERAGE_MARKED_ALIGNMENT_PENDING",
        table=TABLE,
        snapshot_at=snapshot["snapshot_at"],
        entity_count=len(rows),
        qid_count=len(qids),
        entity_row_statuses=dict(
            Counter(r["attributes"]["bq_availability"]["status"] for r in rows)
        ),
        missing_counts_by_scope=dict(Counter(r["scope"] for r in missing)),
        existing_non_bq_full_record_qids=sorted(
            {r["entity_id"] for r in rows if r["reference_source"] == "WIKIDATA"}
        ),
        event_stage_status="PENDING_ROOT_ABSENT_FROM_PINNED_BQ",
        live_wikidata_fallback_allowed=False,
        new_queries=0,
        full_record_alignment_complete=False,
        inputs={
            str(p): digest(p)
            for p in (
                cache / "manifest.json",
                cache / "reference_manifest.json",
                cache / "entity_metadata.json.gz",
                entities / "manifest.json",
                entities / "entities.json.gz",
                store / "table_snapshot.json",
                store / f"{key}.sql",
                store / f"{key}.json.gz",
            )
        },
        code_sha256=digest(Path(__file__)),
        outputs={p.name: digest(p) for p in output.glob("*.json.gz")},
    )
    (output / "manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home()
        / ".cache/geoai_full_daniel_dump_bigquery_parallel_20261019",
    )
    parser.add_argument("--entities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.cache, args.entities, args.output)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "snapshot_at",
                    "entity_count",
                    "entity_row_statuses",
                    "missing_counts_by_scope",
                    "new_queries",
                )
            }
        )
    )

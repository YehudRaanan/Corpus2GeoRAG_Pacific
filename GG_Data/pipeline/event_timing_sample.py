"""Time unrestricted discovery and Event checks for random frozen Daniel rows.

Population S2T sections 7/8: start with Daniel, count the union of direct links
in both directions, then use the approved latest hierarchy. This benchmark
does not add model rows, change matching, or cap Event candidates.
"""

from __future__ import annotations

import gzip
import json
import logging
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.mapping.build_relation_mapping_v2_1 import read_csv
from GG_Data.pipeline import events
from GG_Data.pipeline.event_candidate_check import qualifying_links
from GG_Data.pipeline.event_candidate_ids import MEASUREMENT_TAIL
from GG_Data.pipeline.event_on_demand import event_path, fetch_classes
from GG_Data.pipeline.event_sample_query import BASE, sample_query
from GG_Data.pipeline.event_snapshot_discovery import measure_query
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def candidate_endpoints(incoming: list[dict], outgoing: dict, daniel: set) -> dict:
    """Apply the same >=2 distinct-QID gate before expensive classification.

    This is only a preliminary native-link gate: mapping/exclusions must still
    pass after classification. Repeated links and both directions count once.
    """
    combined = {q: set(targets) for q, targets in outgoing.items()}
    seen = set()
    for row in incoming:
        qid, targets = row["id"], row["targets"]
        if (
            not re.fullmatch(r"Q[1-9]\d*", qid)
            or qid in seen
            or not targets
            or not set(targets) <= daniel
        ):
            raise SourceException("Unexpected incoming candidate inventory", row=row)
        seen.add(qid)
        combined.setdefault(qid, set()).update(targets)
    return {q: sorted(targets) for q, targets in combined.items() if len(targets) >= 2}


def native_rank_answers(saved: dict) -> dict:
    """Adapt verified SPARQL rank URLs to the on-demand reader's native ranks.

    S2T 7 already excludes deprecated ancestry. The old probe stores rank URIs;
    fetch_classes returns native rank names. Keep the raw cache unchanged.
    """
    events.classify_events(saved)  # Reject unknown ranks/incomplete ancestry.
    return {
        prop: {
            qid: [
                dict(
                    edge,
                    rank=edge["rank"].rsplit("#", 1)[-1].removesuffix("Rank").lower(),
                )
                for edge in answers
            ]
            for qid, answers in rows.items()
        }
        for prop, rows in saved.items()
    }


def run() -> dict:
    output = BASE / "poc_10k_event_timing_100_mentions_200_candidates_20261020"
    if output.exists():
        raise ValueError("Keep previous benchmark evidence unchanged")
    mentions = BASE / "poc_10k/mentions.json.gz"
    entities = BASE / "poc_10k_entities_snapshot_first_20261020"
    prior = BASE / "poc_10k_event_sample_query_20261020"
    hierarchy = BASE / "poc_10k_current_event_rate_limit_retry_20261020"
    store = BASE / "wikidata_event_snapshot_discovery_cache"
    live_store = BASE / "wikidata_current_event_cache"
    previous = read_json(prior / "report.json")
    if (
        digest(prior / "report.json")
        != read_json(prior / "verification.json")["report_sha256"]
    ):
        raise SourceException("Verified small query test changed")
    for name, sha in previous["inputs"].items():
        if digest(ROOT / name) != sha:
            raise SourceException("Saved benchmark reference changed", file=name)
    manifest = read_json(entities / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(entities / name) != sha:
            raise SourceException("Frozen Entity output changed", file=name)
    if (
        digest(mentions)
        != read_json(mentions.parent / "manifest.json")["outputs"][mentions.name]
    ):
        raise SourceException("Frozen Daniel Mentions changed")
    reference = next(
        ROOT / p for p in previous["inputs"] if p.endswith("reference_manifest.json")
    )
    ref = read_json(reference)
    if read_json(store / "table_snapshot.json") != ref["table_snapshot"]:
        raise SourceException("Benchmark cache snapshot differs")
    # Reuse complete saved current hierarchy answers. A partial catalog is not
    # used as negative evidence, and snapshot P31 never replaces this evidence.
    for name, sha in read_json(hierarchy / "verification.json")["outputs"].items():
        if digest(hierarchy / name) != sha:
            raise SourceException("Accepted hierarchy evidence changed", file=name)
    for row in read_json(hierarchy / "probe.json")["queries"]:
        source = row["source"]
        if digest(ROOT / source["cache"] / "response.json") != source["sha256"]:
            raise SourceException("Hierarchy raw response changed")
    saved_classes = native_rank_answers(read_json(hierarchy / "hierarchy_edges.json"))
    parents = dict(saved_classes["P279"])
    rows = random.Random(20261020).sample(read_json(mentions), 100)
    daniel = {
        r["entity_id"]
        for r in rows
        if r["raw"]["entity_group"] != "DATE"
        and re.fullmatch(r"Q[1-9]\d*", r.get("entity_id") or "")
    }
    records = read_json(entities / "full_records.json.gz")
    outgoing = {}
    for qid in sorted(daniel):
        for link in events.item_links(records[qid]["entity"]):
            outgoing.setdefault(link["object_qid"], set()).add(qid)
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from bigquery_direct_wikidata import BigQueryData
    finally:
        sys.path.pop(0)
    client = BigQueryData(ref["project"], store)
    output.mkdir()
    (output / "benchmark_code_at_launch.py").write_bytes(Path(__file__).read_bytes())
    began = time.perf_counter()
    report = dict(
        status="DISCOVERING_CANDIDATES",
        seed=20261020,
        sampled_mentions=100,
        distinct_matched_daniel_qids=len(daniel),
        started_at=datetime.now(timezone.utc).isoformat(),
        candidate_count=None,
        candidates_classified=0,
        hierarchy_positive_count=0,
        source_answers=0,
        stages_seconds={},
        events_complete=False,
        event_rows_written=0,
        final_graph_written=False,
        scope="SAMPLE_DISCOVERY_CLASSIFICATION_AND_LINK_QUALIFICATION_ONLY",
        timing_candidate_sample_size=200,
        timed_batches=[],
        code_sha256=digest(Path(__file__)),
        inputs={
            str(p): digest(p)
            for p in (
                mentions,
                entities / "manifest.json",
                prior / "report.json",
                hierarchy / "verification.json",
            )
        },
    )

    def save():
        report["elapsed_seconds"] = round(time.perf_counter() - began, 3)
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    def receipt(row):
        with (output / "source_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        report["source_answers"] += 1
        save()

    def fetch(batch, prop):
        return fetch_classes(live_store, batch, prop, receipt)

    (output / "sample.json").write_text(
        json.dumps(
            {
                "mention_ids": [r["mention_id"] for r in rows],
                "daniel_qids": sorted(daniel),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    save()
    try:
        sql = measure_query(client.source, daniel, set(outgoing))
        if not sql.endswith(MEASUREMENT_TAIL):
            raise SourceException("Unexpected discovery query structure")
        sql = sql[: -len(MEASUREMENT_TAIL)] + "\nSELECT id, targets FROM candidates"
        (output / "discovery.sql").write_text(sql, encoding="utf-8")
        incoming = client.query(sql)
        with gzip.open(
            output / "incoming_candidates.json.gz", "wt", encoding="utf-8"
        ) as f:
            json.dump(incoming, f)
        candidates = candidate_endpoints(incoming, outgoing, daniel)
        with gzip.open(
            output / "candidate_endpoints.json.gz", "wt", encoding="utf-8"
        ) as f:
            json.dump(candidates, f)
        report.update(
            candidate_count=len(candidates),
            incoming_candidate_count=len(incoming),
            status="CLASSIFYING_CANDIDATES",
            discovery_source=client.requests[-1],
        )
        report["stages_seconds"]["discovery"] = round(time.perf_counter() - began, 3)
        save()
        LOG.info(
            "Discovered %s candidates for %s Daniel QIDs", len(candidates), len(daniel)
        )
        # This is a timing experiment, not candidate population. Retain the
        # complete discovered inventory, then draw independent random work units
        # to estimate classification throughput without a low-QID ordering bias.
        # No untested item is rejected and no model Event table is produced.
        ordered = random.Random(20261020).sample(
            sorted(candidates), min(200, len(candidates))
        )
        (output / "timing_candidate_qids.json").write_text(
            json.dumps(ordered), encoding="utf-8"
        )
        report["timed_candidate_count"] = len(ordered)
        classified = []
        stage_start = time.perf_counter()
        with (output / "classifications.jsonl").open("a", encoding="utf-8") as f:
            for offset in range(0, len(ordered), 10):
                batch_start = time.perf_counter()
                answers_before = report["source_answers"]
                batch = ordered[offset : offset + 10]
                missing = [q for q in batch if q not in saved_classes["P31"]]
                direct = {q: saved_classes["P31"][q] for q in batch if q not in missing}
                if missing:
                    direct.update(fetch(missing, "P31"))
                for qid in batch:
                    report["current_qid"] = qid
                    save()
                    proof = None
                    for edge in direct[qid]:
                        if edge["rank"] == "deprecated":
                            continue
                        path = event_path(edge["parent"], parents, {}, fetch)
                        if path is not None:
                            proof = dict(P31=edge, P279=path)
                            break
                    case = dict(
                        qid=qid,
                        event_hierarchy_match=proof is not None,
                        proof=proof,
                        P31=direct[qid],
                    )
                    classified.append(case)
                    f.write(json.dumps(case) + "\n")
                    f.flush()
                    report["candidates_classified"] += 1
                    report["hierarchy_positive_count"] += int(proof is not None)
                    report["stages_seconds"]["classification"] = round(
                        time.perf_counter() - stage_start, 3
                    )
                    save()
                report["timed_batches"].append(
                    dict(
                        count=len(batch),
                        seconds=round(time.perf_counter() - batch_start, 3),
                        source_answers=report["source_answers"] - answers_before,
                    )
                )
                save()
                LOG.info(
                    "Classified %s/%s; Event-positive=%s",
                    len(classified),
                    len(ordered),
                    report["hierarchy_positive_count"],
                )
        positives = [r for r in classified if r["event_hierarchy_match"]]
        report["status"] = "QUALIFYING_EVENT_LINKS"
        save()
        stage_start = time.perf_counter()
        decisions = []
        if positives:
            sql = sample_query(client.source, sorted(daniel), classified)
            (output / "qualification.sql").write_text(sql, encoding="utf-8")
            answer = client.query(sql)
            report["qualification_source"] = client.requests[-1]
            if len(answer) != 1 or not (daniel | {r["qid"] for r in positives}) <= set(
                answer[0]["present_qids"]
            ):
                raise SourceException(
                    "Incomplete snapshot Event qualification response"
                )
            (output / "qualification_result.json").write_text(
                json.dumps(answer), encoding="utf-8"
            )
            mapping_path = next(
                ROOT / p
                for p in previous["inputs"]
                if p.endswith("RELATION_MAPPING_TABLE_v2.1.2.csv")
            )
            mapping = {
                (r["source"], r["source_predicate"]): r for r in read_csv(mapping_path)
            }
            by_event = {}
            for row in answer[0]["links"]:
                links = events.item_links(
                    dict(
                        id=row["subject_qid"],
                        claims={
                            row["property_id"]: [json.loads(row["statement_json"])]
                        },
                    )
                )
                if len(links) != 1 or links[0]["object_qid"] != row["object_qid"]:
                    raise SourceException("Unexpected qualification native statement")
                by_event.setdefault(row["event_qid"], []).extend(links)
            for case in positives:
                qid = case["qid"]
                kept, excluded = qualifying_links(
                    by_event.get(qid, []), qid, daniel, mapping
                )
                targets = sorted({r["daniel_qid"] for r in kept})
                decisions.append(
                    dict(
                        qid=qid,
                        eligible=len(targets) >= 2,
                        daniel_qids=targets,
                        links=kept,
                        excluded=excluded,
                    )
                )
        (output / "decisions.json").write_text(
            json.dumps(decisions, indent=2), encoding="utf-8"
        )
        report["stages_seconds"]["qualification"] = round(
            time.perf_counter() - stage_start, 3
        )
        report.update(
            status="TIMING_SAMPLE_COMPLETE",
            qualified_event_qids=[r["qid"] for r in decisions if r["eligible"]],
        )
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        report.update(
            status="BLOCKED_TIMING_SAMPLE",
            exception=getattr(exc, "case", {"reason": str(exc)}),
        )
        LOG.error("Benchmark stopped: %s", report["exception"]["reason"])
    (output / "class_parents.json").write_text(json.dumps(parents), encoding="utf-8")
    report["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    save()
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("bigquery_direct_wikidata").setLevel(logging.WARNING)
    result = run()
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in (
                    "status",
                    "sampled_mentions",
                    "distinct_matched_daniel_qids",
                    "candidate_count",
                    "candidates_classified",
                    "hierarchy_positive_count",
                    "elapsed_seconds",
                    "exception",
                )
            }
        )
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

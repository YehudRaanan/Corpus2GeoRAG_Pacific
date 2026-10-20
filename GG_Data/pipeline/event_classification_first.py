"""Bounded classification-first retrieval test; population S2T section 7.

Use the verified current hierarchy probe, not the unclassified 2.21M pool.
Positive ancestry permits record acquisition only; it does not include an Event.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from pathlib import Path

from GG_Data.pipeline import entities, events
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException


def run(prior: Path, available: Path, store: Path, output: Path) -> dict:
    """Classify before requesting full records, keeping snapshot assertions.

    S2T 1/7: the current hierarchy is a classification-only exception. Native
    records still use the pinned snapshot, with approved same-QID fallback.
    This test neither expands the probe nor estimates full-population coverage.
    """
    if output.exists() or any(
        not p.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs")
        for p in (store, output)
    ):
        raise ValueError("Use a new approved pipeline output directory")
    check = read_json(prior / "verification.json")
    report = read_json(prior / "report.json")
    if (
        check["status"] != "VERIFIED_MEASUREMENT_ONLY_DOWNLOAD_PENDING_CONSULTATION"
        or digest(prior / "report.json") != check["report_sha256"]
    ):
        raise ValueError("Expected verified candidate measurement")
    for name, sha in report["inputs"].items():
        if digest(Path(name)) != sha:
            raise ValueError(f"Measurement input changed: {name}")
    for name, sha in report["outputs"].items():
        if digest(prior / name) != sha:
            raise ValueError(f"Measurement output changed: {name}")
    inputs = [Path(name) for name in report["inputs"]]
    hierarchy = next(p for p in inputs if p.name == "hierarchy_edges.json")
    reference = next(p for p in inputs if p.name == "reference_manifest.json")
    # Never substitute snapshot P31 for current classification evidence.
    classified = events.classify_events(read_json(hierarchy))
    if classified != read_json(prior / "classifications.json"):
        raise ValueError("Saved hierarchy classification differs")
    selected = {r["qid"] for r in classified if r["event_hierarchy_match"]}
    fallback_check = read_json(available / "verification.json")
    fallback_report = read_json(available / "report.json")
    if digest(available / "report.json") != fallback_check["outputs"]["report.json"]:
        raise ValueError("Saved candidate source report changed")
    sources = {r["qid"]: r["source"] for r in fallback_report["records"]}
    fallback = {}
    for qid in sorted(selected):
        path = available / f"{qid}.json"
        if digest(path) != fallback_check["outputs"][path.name]:
            raise ValueError(f"Saved candidate record changed: {qid}")
        envelope = dict(requested_qid=qid, entity=read_json(path))
        entities.native_record(envelope, qid)
        fallback[qid] = [(envelope, sources[qid])]
    output.mkdir(parents=True)
    result = dict(
        status="CLASSIFIED_BEFORE_FULL_RECORD_ACQUISITION",
        scope="VERIFIED_CACHED_HIERARCHY_PROBE_ONLY",
        candidate_count=len(classified),
        hierarchy_positive_qids=sorted(selected),
        full_record_qids_requested=sorted(selected),
        events_complete=False,
        event_rows_written=0,
        final_graph_written=False,
        inputs={
            str(p): digest(p)
            for p in (
                prior / "report.json",
                prior / "verification.json",
                available / "verification.json",
            )
        },
        code_sha256=digest(Path(__file__)),
    )
    (output / "classifications.json").write_text(json.dumps(classified, indent=2))
    # Write the pre-acquisition decision first, so ordering is reviewable.
    (output / "report.json").write_text(json.dumps(result, indent=2))
    try:
        records, provenance = entities.acquire_missing(
            selected, store, read_json(reference), available_records=fallback
        )
        if set(records) != selected or set(provenance) != selected:
            raise ValueError("Full records differ from classified candidate selection")
        for qid, envelope in records.items():
            entities.native_record(envelope, qid)
        with gzip.open(output / "full_records.json.gz", "wt", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, allow_nan=False)
        (output / "provenance.json").write_text(json.dumps(provenance, indent=2))
        result.update(
            status="CLASSIFICATION_FIRST_RETRIEVAL_TEST_COMPLETE",
            full_records_retained=len(records),
            record_providers={
                qid: p.get("provider", "WIKIDATA") for qid, p in provenance.items()
            },
        )
    except (ValueError, RuntimeError, SourceException) as exc:
        # POC stop rule: no silent retry, broader fetch or fallback rule change.
        result.update(status="BLOCKED_CLASSIFICATION_FIRST_TEST", error=str(exc))
    result["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    (output / "report.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prior", "available", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(args.prior, args.available, args.store, args.output)
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"inputs", "outputs"}})
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

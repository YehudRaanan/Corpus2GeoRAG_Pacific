"""Approved Canada retrieval test: population S2T 7, one property per request.

Only P17 is tested here, on the main query graph. Passing this test cannot
establish full incoming coverage or authorize classifying the partial inventory.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.event_discovery import incoming_pages
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException


def run(source: Path, scores: Path, store: Path, output: Path) -> dict:
    """Verify prior evidence and score preparation before a single-property test."""
    if output.exists() or not output.resolve().is_relative_to(
        ROOT / "GG_Data/pipeline/outputs"
    ):
        raise ValueError("Use a new approved pipeline output directory")
    previous = read_json(source / "verification.json")
    if previous["status"] != "VERIFIED_PAGED_DISCOVERY_SOURCE_STOP_ONLY":
        raise SourceException("Expected verified paged discovery stop")
    score_manifest = read_json(scores / "manifest.json")
    score_check = read_json(scores / "verification.json")
    if (
        score_check["status"] != "VERIFIED_ENTITIES_IMPORTANCE_INCLUDING_SYNTHETICS"
        or digest(scores / "manifest.json") != score_check["manifest_sha256"]
    ):
        raise SourceException("Expected verified Entity importance before retrieval")
    for directory, hashes in (
        (source, previous["outputs"]),
        (scores, score_manifest["outputs"]),
    ):
        for name, sha in hashes.items():
            if digest(directory / name) != sha:
                raise SourceException(
                    "Property test input checksum differs", file=str(directory / name)
                )
    report = dict(
        status="RUNNING_PROPERTY_RETRIEVAL_TEST",
        qid="Q16",
        property_id="P17",
        graph=events.QUERY_URL,
        page_size=5000,
        pages=[],
        statements=0,
        property_complete=False,
        full_10k_event_discovery_complete=False,
        event_population_complete=False,
        event_rows_written=0,
        capped_relations_written=0,
        source_verification_sha256=digest(source / "verification.json"),
        score_manifest_sha256=digest(scores / "manifest.json"),
        code_sha256=digest(Path(__file__)),
    )
    output.mkdir(parents=True)
    report_path = output / "report.json"

    def save() -> None:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    save()
    try:
        for number, (links, evidence, complete) in enumerate(
            incoming_pages(store, events.QUERY_URL, "Q16", 5000, property_id="P17"), 1
        ):
            destination = output / f"incoming_P17_{number:05d}.json.gz"
            with gzip.open(destination, "wt", encoding="utf-8") as stream:
                json.dump(links, stream, ensure_ascii=False)
            report["pages"].append(
                dict(
                    file=destination.name,
                    sha256=digest(destination),
                    source=evidence,
                    statements=len(links),
                )
            )
            report["statements"] += len(links)
            report["property_complete"] = complete
            save()
            logging.info(
                "Canada P17 saved page %s: %s statements; terminal=%s",
                number,
                len(links),
                complete,
            )
        report["status"] = "PROPERTY_RETRIEVAL_TEST_PASSED"
    except SourceException as exc:
        report.update(status="BLOCKED_PROPERTY_RETRIEVAL_TEST", exception=exc.case)
    except (KeyError, TypeError, ValueError) as exc:
        report.update(
            status="BLOCKED_PROPERTY_RETRIEVAL_TEST",
            exception=dict(reason="Malformed property response", error=str(exc)),
        )
    finally:
        save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "scores", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(args.source, args.scores, args.store, args.output)
    print(
        json.dumps(
            {key: result[key] for key in ("status", "statements", "property_complete")}
        )
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

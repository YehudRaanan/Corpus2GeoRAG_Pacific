"""Intersect current Event instances with snapshot candidates; population S2T 7.

Enumerating native P31 links to the completed Event-class catalog avoids a
separate class request for each of the 2.21M candidate IDs. This is reference
classification only: it creates no Daniel mention, Entity row or model Event.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.event_class_catalog import reverse_pages
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def verified_inputs(catalog: Path, candidates: Path, measurement: Path):
    """Require complete ancestry and the unchanged original candidate universe.

    The incoming snapshot pool alone is insufficient: union the local outgoing
    inventory, as required by S2T 7's direct-link rule in either direction.
    """
    report = read_json(catalog / "report.json")
    if report["status"] != "CURRENT_EVENT_CLASS_CATALOG_COMPLETE_FOR_QUERY_GRAPHS":
        raise ValueError("Current Event class catalog is incomplete")
    if digest(catalog / "catalog.json") != report["outputs"]["catalog.json"]:
        raise ValueError("Class catalog changed")
    for receipt in report["queries"]:
        source = receipt["source"]
        if digest(Path(source["cache"]) / "response.json") != source["sha256"]:
            raise ValueError("Class source response changed")
    data = read_json(catalog / "catalog.json")
    classes = set(data["classes"])
    if (
        classes != set(data["completed"])
        or events.EVENT_ROOT not in classes
        or len(classes) != report["class_count"]
    ):
        raise ValueError("Class catalog coverage differs")
    check = read_json(candidates / "verification.json")
    candidate_report = read_json(candidates / "report.json")
    if (
        check["status"] != "VERIFIED_SNAPSHOT_CANDIDATE_IDS_ONLY"
        or digest(candidates / "report.json") != check["report_sha256"]
    ):
        raise ValueError("Expected verified snapshot candidate IDs")
    for name, sha in candidate_report["outputs"].items():
        if digest(candidates / name) != sha:
            raise ValueError("Candidate IDs changed")
    if candidate_report["inputs"].get(str(measurement / "report.json")) != digest(
        measurement / "report.json"
    ):
        raise ValueError("Candidate measurement lineage differs")
    measured = read_json(measurement / "report.json")
    for name, sha in measured["inputs"].items():
        if digest(Path(name)) != sha:
            raise ValueError(f"Measurement input changed: {name}")
    records_path = next(
        Path(p) for p in measured["inputs"] if Path(p).name == "full_records.json.gz"
    )
    outgoing = {
        link["object_qid"]
        for envelope in read_json(records_path).values()
        for link in events.item_links(envelope["entity"])
    }
    incoming = set(read_json(candidates / "candidate_ids.json.gz"))
    if (
        len(incoming) != candidate_report["candidate_count"]
        or len(outgoing) != measured["outgoing_reference_qids"]
    ):
        raise ValueError("Candidate universe differs from saved measurement")
    return sorted(classes, key=lambda q: int(q[1:])), incoming | outgoing


def run(catalog: Path, candidates: Path, measurement: Path, store: Path, output: Path):
    if output.exists() or any(
        not p.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs")
        for p in (store, output)
    ):
        raise ValueError("Use a new approved pipeline output directory")
    classes, universe = verified_inputs(catalog, candidates, measurement)
    output.mkdir(parents=True)
    result = dict(
        status="RETRIEVING_CURRENT_EVENT_INSTANCE_CLASSES",
        scope="BOTH_CURRENT_QUERY_GRAPHS_P31_INTERSECT_SNAPSHOT_CANDIDATES",
        root=events.EVENT_ROOT,
        class_count=len(classes),
        candidate_universe_count=len(universe),
        completed_classes=0,
        queries=[],
        event_rows_written=0,
        events_complete=False,
        classification_complete=False,
        final_graph_written=False,
        inputs={
            str(p): digest(p)
            for p in (
                catalog / "report.json",
                catalog / "catalog.json",
                candidates / "report.json",
                candidates / "verification.json",
                measurement / "report.json",
            )
        },
        code_sha256=digest(Path(__file__)),
    )
    matches = {}

    def save():
        # Keep only relevant positive evidence here; complete untouched pages,
        # including deprecated/non-population records, remain in the cache.
        positives = sorted({link["subject_qid"] for link in matches.values()})
        result["hierarchy_positive_count"] = len(positives)
        (output / "positive_qids.json").write_text(
            json.dumps(positives), encoding="utf-8"
        )
        with gzip.open(
            output / "positive_p31_links.json.gz", "wt", encoding="utf-8"
        ) as f:
            json.dump(list(matches.values()), f)
        (output / "report.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

    save()
    try:
        for start in range(0, len(classes), 10):
            batch = classes[start : start + 10]
            for url in (events.QUERY_URL, events.SCHOLARLY_QUERY_URL):
                for links, receipt in reverse_pages(store, url, batch, "P31"):
                    result["queries"].append(receipt)
                    for link in links:
                        if (
                            link["subject_qid"] in universe
                            and link["rank"] != "deprecated"
                        ):
                            key = link["source_record_id"]
                            if key in matches and matches[key] != link:
                                raise SourceException(
                                    "Conflicting instance statement", statement=key
                                )
                            matches[key] = link
                    save()
            result["completed_classes"] += len(batch)
            save()
            LOG.info(
                "Instance classes checked=%s/%s; positive candidates=%s",
                result["completed_classes"],
                len(classes),
                result["hierarchy_positive_count"],
            )
        result.update(
            status="CURRENT_EVENT_CANDIDATE_CLASSIFICATION_COMPLETE_FOR_QUERY_GRAPHS",
            classification_complete=True,
        )
    except SourceException as exc:
        result.update(
            status="BLOCKED_CURRENT_EVENT_INSTANCE_CLASSES", exception=exc.case
        )
        LOG.error("Stopped: %s", exc.case["reason"])
    except (KeyError, TypeError, ValueError) as exc:
        result.update(
            status="BLOCKED_CURRENT_EVENT_INSTANCE_CLASSES",
            exception=dict(reason="Malformed instance response", error=str(exc)),
        )
        LOG.error("Stopped: malformed instance response")
    save()
    result["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("catalog", "candidates", "measurement", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(
        args.catalog, args.candidates, args.measurement, args.store, args.output
    )
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"queries", "inputs"}})
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

"""Check the seven probe candidates; population S2T 7, not full discovery.

Use the approved saved hierarchy and cache current native candidate records.
This stage checks their native P31 evidence; the separate direct-link gate is
still pending. No new Daniel entity, matching decision, model Event row, or
graph assertion is created here.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def run(source: Path, output: Path, store: Path) -> dict:
    """Approve the saved classification and inspect native candidates first.

    The immutable earlier diagnostic is evidence, not a mutable run state.
    Save after each request so any data exception stops with a visible record.
    """
    verification = read_json(source / "verification.json")
    for name, sha in verification["outputs"].items():
        if digest(source / name) != sha:
            raise SourceException("Candidate source checksum mismatch", file=name)
    classified = events.classify_events(read_json(source / "hierarchy_edges.json"))
    candidates = [row for row in classified if row["event_hierarchy_match"]]
    output.mkdir(parents=True, exist_ok=False)
    (output / "classifications.json").write_text(
        json.dumps(classified, indent=2), encoding="utf-8"
    )
    report = dict(
        status="CHECKING_NATIVE_CANDIDATES",
        classification_rule="event-nondeprecated-P31-P279-v1",
        root=events.EVENT_ROOT,
        hierarchy_source=str(source),
        hierarchy_sha256=digest(source / "hierarchy_edges.json"),
        candidates=[row["qid"] for row in candidates],
        records=[],
        event_rows_written=0,
        event_population_complete=False,
    )

    def save() -> None:
        (output / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    save()
    try:
        for candidate in candidates:
            qid = candidate["qid"]
            record, evidence = events.current_record(store, qid)
            links = events.item_links(record)
            # Native P31 must still support the saved query-service path. A
            # changed source is a visible stop, not an automatic reclassification.
            p31 = {
                link["source_record_id"].replace("$", "-").lower(): link
                for link in links
                if link["source_predicate"] == "wd:P31"
            }
            for path in candidate["paths"]:
                edge = path["P31"]
                sid = edge["statement"].rsplit("/", 1)[-1].replace("$", "-").lower()
                link = p31.get(sid)
                if (
                    not link
                    or link["object_qid"] != edge["parent"]
                    or link["raw_statement"]["rank"] == "deprecated"
                ):
                    raise SourceException(
                        "Native candidate differs from saved Event classification",
                        qid=qid,
                        edge=edge,
                        source=evidence,
                    )
            (output / f"{qid}.json").write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
            report["records"].append(
                dict(
                    qid=qid,
                    name=record.get("labels", {}).get("en", {}).get("value")
                    or record.get("labels", {}).get("ja", {}).get("value"),
                    labels=record.get("labels", {}),
                    descriptions=record.get("descriptions", {}),
                    revision=record["lastrevid"],
                    P31=[
                        link for link in links if link["source_predicate"] == "wd:P31"
                    ],
                    source=evidence,
                )
            )
            save()
            LOG.info("Saved candidate %s: %s", qid, report["records"][-1]["name"])
        report["status"] = "NATIVE_CANDIDATES_CHECKED_LINK_GATE_PENDING"
    except SourceException as exc:
        report.update(status="BLOCKED_CANDIDATE_CHECK", exception=exc.case)
        LOG.error("Stopped: %s", exc.case["reason"])
    finally:
        save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(args.source, args.output, args.store)
    print(json.dumps(dict(status=result["status"], records=len(result["records"]))))
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

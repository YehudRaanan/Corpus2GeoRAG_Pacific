"""Resume the saved five-QID source probe; not a complete Event population.

Population S2T 7: direct P31/P279 evidence only, all ranks and no depth limit.
Candidate classes remain supporting data; this module writes no model entities.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def resume(prior: Path, output: Path, store: Path) -> dict:
    """Keep the old run immutable and count its failed request as attempt one."""
    report = read_json(prior / "probe.json")
    verification = read_json(prior / "verification.json")
    if report["status"] != "BLOCKED_HIERARCHY_PROBE":
        raise SourceException("Expected the saved interrupted hierarchy probe")
    for name, expected in verification["outputs"].items():
        if digest(prior / name) != expected:
            raise SourceException("Prior probe checksum mismatch", file=name)
    if digest(prior / "probe.json") != verification["probe_sha256"]:
        raise SourceException("Prior probe report checksum mismatch")
    # Verify all successful source bytes without making another request.
    for query in report["queries"]:
        evidence = query["source"]
        if digest(Path(evidence["cache"]) / "response.json") != evidence["sha256"]:
            raise SourceException("Prior source checksum mismatch", tag=query["tag"])
    failed = report.pop("exception")
    edges = read_json(prior / "hierarchy_edges.json")
    output.mkdir(parents=True, exist_ok=False)
    report.update(
        status="RUNNING_HIERARCHY_PROBE",
        resumed_from=str(prior),
        resumed_probe_sha256=digest(prior / "probe.json"),
        retry_policy={
            "http_statuses": [429, 502, 503, 504],
            "attempts": 3,
            "waits": [10, 30],
            "respect_retry_after": True,
            "request_pause_seconds": 5,
        },
    )

    def save() -> None:
        report.update(P31_nodes=len(edges["P31"]), P279_nodes=len(edges["P279"]))
        for name, data in (("hierarchy_edges.json", edges), ("probe.json", report)):
            (output / name).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def fetch(batch: list[str], prop: str) -> None:
        query = events.class_edges_query(batch, prop)
        tag = f"{prop}_{len(report['queries']):04d}"
        (output / f"{tag}.sparql").write_text(query, encoding="utf-8")
        data, evidence = events.cached_json(
            store, events.QUERY_URL, {"query": query, "format": "json"}
        )
        report["queries"].append(dict(tag=tag, source=evidence))
        target = {qid: [] for qid in batch}
        seen = set()
        absent = set()
        for row in data["results"]["bindings"]:
            item = row["item"]["value"]
            if not re.fullmatch(r"http://www.wikidata.org/entity/Q[1-9]\d*", item):
                raise SourceException("Unexpected hierarchy item", item=item)
            qid = item.rsplit("/", 1)[-1]
            if qid not in target or row["present"]["value"] not in {"true", "false"}:
                raise SourceException("Unexpected hierarchy batch response", qid=qid)
            seen.add(qid)
            if row["present"]["value"] == "false":
                absent.add(qid)
            if "parent" in row:
                parent = row["parent"]["value"]
                if not re.fullmatch(
                    r"http://www.wikidata.org/entity/Q[1-9]\d*", parent
                ):
                    raise SourceException("Unexpected hierarchy parent", parent=parent)
                target[qid].append(
                    dict(
                        parent=parent.rsplit("/", 1)[-1],
                        statement=row["statement"]["value"],
                        rank=row["rank"]["value"],
                    )
                )
        if seen != set(batch):
            raise SourceException(
                "Incomplete hierarchy batch", missing=sorted(set(batch) - seen)
            )
        for qid in absent:
            # Approved native-record coverage check, never a guessed parent.
            record, native_source = events.current_record(store, qid)
            report.setdefault("native_fallbacks", []).append(
                dict(qid=qid, source=native_source)
            )
            target[qid] = [
                dict(
                    parent=link["object_qid"],
                    statement=link["source_record_id"],
                    rank=link["raw_statement"]["rank"],
                )
                for link in events.item_links(record)
                if link["source_predicate"] == f"wd:{prop}"
            ]
        edges[prop].update(target)
        save()
        LOG.info(
            "Saved P31=%s, P279=%s; source requests=%s",
            len(edges["P31"]),
            len(edges["P279"]),
            len(report["queries"]),
        )

    save()
    try:
        # Resume the exact failed query first, including its existing attempt budget.
        failed_query = failed["request"]["params"]["query"]
        batch = re.findall(r"wd:(Q[1-9]\d*)", failed_query)
        if failed_query != events.class_edges_query(batch, "P279"):
            raise SourceException("Unexpected saved failed hierarchy query")
        fetch(batch, "P279")
        while True:
            parents = {
                edge["parent"]
                for group in edges.values()
                for rows in group.values()
                for edge in rows
            }
            pending = sorted(
                parents - set(edges["P279"]) - {events.EVENT_ROOT},
                key=lambda q: int(q[1:]),
            )
            if not pending:
                break
            for offset in range(0, len(pending), 10):
                fetch(pending[offset : offset + 10], "P279")
        classifications = events.classify_events(edges)
        (output / "candidate_classifications.json").write_text(
            json.dumps(classifications, indent=2), encoding="utf-8"
        )
        report.update(
            status="HIERARCHY_PROBE_ONLY",
            event_hierarchy_matches=[
                r["qid"] for r in classifications if r["event_hierarchy_match"]
            ],
            event_population_complete=False,
        )
    except SourceException as exc:
        report.update(status="BLOCKED_HIERARCHY_PROBE", exception=exc.case)
        LOG.error("Stopped: %s", exc.case["reason"])
    except (KeyError, TypeError) as exc:
        # Malformed source data is never a retryable service failure.
        report.update(
            status="BLOCKED_HIERARCHY_PROBE",
            exception=dict(reason="Malformed hierarchy source data", error=str(exc)),
        )
        LOG.error("Stopped: malformed hierarchy source data")
    finally:
        save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    result = resume(args.prior, args.output, args.store)
    print(
        json.dumps(
            {
                key: result.get(key)
                for key in (
                    "status",
                    "P31_nodes",
                    "P279_nodes",
                    "event_hierarchy_matches",
                    "event_population_complete",
                )
            }
        )
    )
    raise SystemExit(0 if result["status"] == "HIERARCHY_PROBE_ONLY" else 1)

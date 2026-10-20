"""Discover direct Event reference candidates for the frozen Daniel population.

Population S2T 7: reuse full native outgoing records and the approved single-QID
incoming query on both Wikidata graphs. This is acquisition, not classification
or model population. Candidate QIDs never become new Daniel entities here.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.event_candidate_check import incoming_links
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def incoming_pages(
    store: Path, url: str, qid: str, size: int
) -> Iterator[tuple[list[dict], dict, bool]]:
    """Reuse complete old results, otherwise read a complete ordered page chain.

    The user authorized continuation after approving the uncapped Event scope.
    Raw malformed parents are never reused as data or overwritten. S2T 7/8:
    a short terminal page establishes coverage for this graph/QID request;
    partial JSON, repeated/unsorted cursors and other surprises still stop.
    """
    # Validate size/QID before even inspecting a cache directory.
    events.incoming_page_query(qid, size=size)
    params = {"query": events.incoming_query(qid), "format": "json"}
    receipt = events.cache_path(store, url, params) / "request.json"
    if receipt.exists() and read_json(receipt).get("status") == "OK":
        data, evidence = events.cached_json(store, url, params)
        yield incoming_links(data, qid), dict(evidence, reused_unpaged=True), True
        return
    after = None
    while True:
        params = {
            "query": events.incoming_page_query(qid, after, size),
            "format": "json",
        }
        data, evidence = events.cached_json(store, url, params)
        links = incoming_links(data, qid)
        ids = [link["source_record_id"] for link in links]
        if (
            len(ids) > size
            or ids != sorted(set(ids))
            or (after is not None and any(sid <= after for sid in ids))
        ):
            raise SourceException(
                "Invalid incoming page ordering or population",
                qid=qid,
                after=after,
                source=evidence,
            )
        complete = len(links) < size
        yield links, dict(
            evidence,
            page_size=size,
            cursor_before=after,
            cursor_after=ids[-1] if ids else after,
            terminal=complete,
        ), complete
        if complete:
            return
        after = ids[-1]


def run(
    source: Path,
    mentions: Path,
    saved_entities: Path,
    output: Path,
    store: Path,
    incoming_page_size: int | None = None,
) -> dict:
    """Extend the checked population without altering accepted upstream files.

    Cache requests retain their exact earlier retry budgets. Successful cached
    records and queries are reused. An exception leaves a visible partial
    inventory; incomplete incoming coverage is never a negative Event result.
    """
    verification = read_json(source / "verification.json")
    if verification["status"] != "VERIFIED_SEVEN_CANDIDATE_ELIGIBILITY_ONLY":
        raise SourceException("Expected verified seven-candidate source")
    for name, sha in verification["outputs"].items():
        if digest(source / name) != sha:
            raise SourceException("Accepted candidate output changed", file=name)
    upstream = verification["upstream_output_hashes"]
    for name, sha in upstream.items():
        if digest(Path(name)) != sha:
            raise SourceException("Accepted upstream output changed", file=name)
    if upstream.get(str(mentions)) != digest(mentions):
        raise SourceException("Mention input is not the verified frozen sample")
    # Same D definition as event_candidate_check.check_links; resolved DATE does
    # not remove a QID supplied by an original non-DATE Daniel mention. S2T 7.
    daniel = {
        row["entity_id"]
        for row in read_json(mentions)
        if row["raw"]["entity_group"] != "DATE"
        and re.fullmatch(r"Q[1-9]\d*", row.get("entity_id") or "")
    }
    if len(daniel) != verification["daniel_population"]:
        raise SourceException("Frozen Daniel QID population differs")
    ordered = sorted(daniel, key=lambda q: int(q[1:]))
    if incoming_page_size is not None:
        events.incoming_page_query(ordered[0], size=incoming_page_size)
    output.mkdir(parents=True, exist_ok=False)
    candidates: set[str] = set()
    report = dict(
        status="READING_NATIVE_OUTGOING",
        root=events.EVENT_ROOT,
        source=str(source),
        source_verification_sha256=digest(source / "verification.json"),
        upstream_output_hashes=upstream,
        daniel_qids=ordered,
        native_records_checked=0,
        native_sources=[],
        outgoing_statements=0,
        incoming_sources=[],
        incoming_statements=0,
        incoming_requests_complete=0,
        incoming_pages_complete=0,
        incoming_page_size=incoming_page_size,
        incoming_requests_required=2 * len(daniel),
        incoming_graphs=[events.QUERY_URL, events.SCHOLARLY_QUERY_URL],
        candidate_count=0,
        event_rows_written=0,
        event_population_complete=False,
        full_10k_event_discovery_complete=False,
    )

    def save() -> None:
        report["candidate_count"] = len(candidates)
        (output / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (output / "candidate_qids.json").write_text(
            json.dumps(sorted(candidates, key=lambda q: int(q[1:]))), encoding="utf-8"
        )

    save()
    try:
        checked = set()
        for records, evidence in events.current_records(store, ordered, saved_entities):
            if set(records) - daniel or checked.intersection(records):
                raise SourceException("Outgoing native population differs")
            for record in records.values():
                links = events.item_links(record)
                candidates.update(link["object_qid"] for link in links)
                report["outgoing_statements"] += len(links)
            checked.update(records)
            report["native_records_checked"] = len(checked)
            report["native_sources"].append(
                dict(
                    source=evidence,
                    records=[
                        dict(qid=qid, revision=r["lastrevid"], modified=r["modified"])
                        for qid, r in records.items()
                    ],
                )
            )
            save()
            LOG.info("Outgoing records: %s/%s", len(checked), len(daniel))
        if checked != daniel:
            raise SourceException("Incomplete outgoing population")
        report["status"] = "READING_INCOMING_BOTH_GRAPHS"
        save()
        for qid in ordered:
            # S2T 7: both graphs, all ranks and full coverage. A page LIMIT
            # controls response size only; it never caps the candidate pool.
            query = events.incoming_query(qid)
            for url in report["incoming_graphs"]:
                if incoming_page_size is None:
                    data, evidence = events.cached_json(
                        store, url, {"query": query, "format": "json"}
                    )
                    pages = [(incoming_links(data, qid), evidence, True)]
                else:
                    pages = incoming_pages(store, url, qid, incoming_page_size)
                for links, evidence, complete in pages:
                    candidates.update(link["subject_qid"] for link in links)
                    report["incoming_statements"] += len(links)
                    report["incoming_sources"].append(
                        dict(qid=qid, statements=len(links), source=evidence)
                    )
                    report["incoming_pages_complete"] += 1
                    report["incoming_requests_complete"] += int(complete)
                    save()
                    LOG.info(
                        "Incoming graph/QIDs: %s/%s; saved pages: %s; candidates: %s",
                        report["incoming_requests_complete"],
                        report["incoming_requests_required"],
                        report["incoming_pages_complete"],
                        len(candidates),
                    )
        # The inventory is only a reference population. It still requires the
        # approved non-deprecated hierarchy and two-distinct-Daniel-QID gate.
        report["status"] = "DIRECT_CANDIDATE_ACQUISITION_ONLY"
    except SourceException as exc:
        report.update(status="BLOCKED_EVENT_DISCOVERY", exception=exc.case)
        LOG.error("Stopped: %s", exc.case["reason"])
    except (KeyError, TypeError, ValueError) as exc:
        report.update(
            status="BLOCKED_EVENT_DISCOVERY",
            exception=dict(reason="Malformed discovery source", error=str(exc)),
        )
        LOG.error("Stopped: malformed discovery source")
    finally:
        save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("source", "mentions", "saved-entities", "output", "store"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    parser.add_argument("--incoming-page-size", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(
        args.source,
        args.mentions,
        args.saved_entities,
        args.output,
        args.store,
        args.incoming_page_size,
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("status", "native_records_checked", "candidate_count")
            }
        )
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

"""Versioned Event hierarchy parameters and timed sample filter; population S2T 7.

Export only native P279 statements, with ordered pages and no global COUNT.
Keep all ranks as evidence; only normal/preferred links build Event ancestry.
No partial export can reject a candidate. No Entity or Event rows are created.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from GG_Data.pipeline import events
from GG_Data.pipeline.event_candidate_check import incoming_links, statement_key
from GG_Data.pipeline.event_on_demand import fetch_classes, filtered_candidate_universe
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)
PAGE_SIZE = 1000
SERVICES = (events.QUERY_URL, events.SCHOLARLY_QUERY_URL)


def bulk_page_query(after: str | None = None) -> str:
    """A transport page, never a class/population limit (S2T 7).

    The explicit lexical order and cursor prevent arbitrary OFFSET pages from
    being mistaken for complete coverage. Both services need a short last page.
    """
    if after is not None and not re.fullmatch(
        r"http://www.wikidata.org/entity/statement/[Qq][1-9]\d*-[0-9a-fA-F-]+",
        after,
    ):
        raise ValueError("Expected a native statement URI cursor")
    cursor = f"FILTER(STR(?statement) > {json.dumps(after)})" if after else ""
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?subject ?parent ?property ?statement ?rank WHERE {{
 ?subject p:P279 ?statement .
 ?statement ps:P279 ?parent ; wikibase:rank ?rank .
 BIND(wd:P279 AS ?property)
 FILTER(STRSTARTS(STR(?subject), "http://www.wikidata.org/entity/Q"))
 FILTER(STRSTARTS(STR(?parent), "http://www.wikidata.org/entity/Q"))
 {cursor}
}}
ORDER BY STR(?statement)
LIMIT {PAGE_SIZE}
"""


def page_links(data: dict, after: str | None) -> list[dict]:
    """Reuse native rank/identity validation before accepting a page."""
    result = []
    for row in data["results"]["bindings"]:
        parent = row["parent"]["value"]
        if not re.fullmatch(r"http://www.wikidata.org/entity/Q[1-9]\d*", parent):
            raise SourceException("Unexpected hierarchy parent", row=row)
        link = incoming_links(
            {"results": {"bindings": [row]}}, parent.rsplit("/", 1)[-1]
        )[0]
        if link["source_predicate"] != "wd:P279":
            raise SourceException("Unexpected hierarchy property", row=row)
        result.append(link)
    ids = [r["source_record_id"] for r in result]
    if (
        len(ids) > PAGE_SIZE
        or ids != sorted(set(ids))
        or (after is not None and any(sid <= after for sid in ids))
    ):
        raise SourceException("Incomplete or unordered bulk hierarchy page")
    return result


def create_edge_table(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE hierarchy_edges (
        statement_key TEXT, child_qid TEXT, parent_qid TEXT, statement_rank TEXT,
        source_statement_id TEXT, source_service TEXT, retrieved_at_utc TEXT,
        PRIMARY KEY (statement_key, source_service))"""
    )


def export_parameters(db: sqlite3.Connection, output: Path, complete: bool) -> dict:
    """S2T 7: UNION terminates cycles; ranks filter each hop, not just its ends.

    CSVs are parameter data, not graph nodes. No inferred Event categories or
    levels are assigned. The manifest pins their hashes and source receipts.
    """
    if not complete:
        raise SourceException("Complete hierarchy export is required")
    conflict = db.execute(
        """SELECT statement_key FROM hierarchy_edges GROUP BY statement_key
        HAVING COUNT(DISTINCT child_qid || '|' || parent_qid || '|' || statement_rank)>1
        LIMIT 1"""
    ).fetchone()
    if conflict:
        raise SourceException("Conflicting hierarchy statements", statement=conflict[0])
    if not db.execute(
        "SELECT 1 FROM hierarchy_edges WHERE parent_qid=? OR child_qid=? LIMIT 1",
        (events.EVENT_ROOT, events.EVENT_ROOT),
    ).fetchone():
        raise SourceException("Approved Event root is absent from exported hierarchy")
    db.execute("CREATE INDEX hierarchy_parent ON hierarchy_edges(parent_qid)")
    db.execute(
        """CREATE TABLE event_types AS WITH RECURSIVE closure(qid) AS (
        SELECT ? UNION SELECT e.child_qid FROM hierarchy_edges e
        JOIN closure c ON e.parent_qid=c.qid
        WHERE e.statement_rank IN ('normal','preferred')) SELECT qid FROM closure""",
        (events.EVENT_ROOT,),
    )
    db.execute("CREATE UNIQUE INDEX event_type_qid ON event_types(qid)")
    db.commit()
    queries = {
        "event_types.csv": (
            "SELECT ? AS root_qid, qid AS subtype_qid FROM event_types ORDER BY qid"
        ),
        "event_hierarchy_mapping.csv": """SELECT ? AS root_qid,
        e.child_qid AS child_type_qid, e.parent_qid AS parent_type_qid,
        e.source_statement_id, e.statement_rank, e.source_service, e.retrieved_at_utc
        FROM hierarchy_edges e JOIN event_types c ON e.child_qid=c.qid
        JOIN event_types p ON e.parent_qid=p.qid
        WHERE e.statement_rank IN ('normal','preferred')
        ORDER BY e.child_qid, e.parent_qid, e.source_statement_id, e.source_service""",
    }
    counts = {}
    for name, sql in queries.items():
        cursor = db.execute(sql, (events.EVENT_ROOT,))
        count = 0
        with (output / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([c[0] for c in cursor.description])
            for row in cursor:
                writer.writerow(row)
                count += 1
        counts[name] = count
    return counts


def filter_candidates(parameters: Path, candidates: Path, store: Path) -> dict:
    """Rerun the unchanged 2,680-candidate sample against completed parameters.

    Reuse accepted P31 evidence and the existing ten-QID fetcher; a missing
    item or source error is never a negative. Native link qualification and
    model Event population remain separate from this hierarchy filter.
    """
    started = perf_counter()
    report = read_json(parameters / "report.json")
    if not report["parameter_table_usable"]:
        raise SourceException("Incomplete Event parameters cannot filter candidates")
    for name, sha in report["outputs"].items():
        if digest(parameters / name) != sha:
            raise SourceException("Event parameter output changed", file=name)
    with (parameters / "event_types.csv").open(encoding="utf-8", newline="") as f:
        classes = {r["subtype_qid"] for r in csv.DictReader(f)}
    population, evidence, saved = filtered_candidate_universe(candidates)
    output = parameters / "filter"
    output.mkdir()
    result = dict(
        status="FILTERING_SAMPLE_WITH_EVENT_PARAMETERS",
        candidate_count=len(population),
        candidates_classified=0,
        hierarchy_positive_count=0,
        classification_complete=False,
        events_complete=False,
        event_rows_written=0,
        filter_evidence=evidence,
        inputs={str(parameters / "report.json"): digest(parameters / "report.json")},
        source_receipts=[],
    )

    def save():
        result["filter_elapsed_seconds"] = perf_counter() - started
        (output / "report.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

    save()
    try:
        with (output / "classifications.jsonl").open("w", encoding="utf-8") as f:
            universe = sorted(population, key=lambda q: int(q[1:]))
            for offset in range(0, len(universe), 10):
                batch = universe[offset : offset + 10]
                missing = [q for q in batch if q not in saved["P31"]]
                if missing:
                    saved["P31"].update(
                        fetch_classes(
                            store, missing, "P31", result["source_receipts"].append
                        )
                    )
                for qid in batch:
                    rows = saved["P31"][qid]
                    positive = any(
                        r["rank"] != "deprecated" and r["parent"] in classes
                        for r in rows
                    )
                    f.write(
                        json.dumps(
                            dict(qid=qid, event_hierarchy_match=positive, P31=rows)
                        )
                        + "\n"
                    )
                    result["candidates_classified"] += 1
                    result["hierarchy_positive_count"] += int(positive)
                f.flush()
                save()
                LOG.info(
                    "Filtered %s/%s candidates", offset + len(batch), len(universe)
                )
        result.update(
            status="COMPLETE_SAMPLE_EVENT_HIERARCHY_FILTER",
            classification_complete=True,
        )
    except (SourceException, KeyError, ValueError) as exc:
        result.update(
            status="BLOCKED_SAMPLE_EVENT_HIERARCHY_FILTER",
            exception=getattr(exc, "case", {"reason": str(exc)}),
        )
    result["outputs"] = {
        "classifications.jsonl": digest(output / "classifications.jsonl")
    }
    save()
    return result


def run(store: Path, output: Path, candidates: Path | None = None) -> dict:
    """Persist every validated page; publish parameters only after both terminals."""
    if output.exists() or any(
        not p.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs")
        for p in (store, output)
    ):
        raise ValueError("Use a new approved pipeline output directory")
    output.mkdir(parents=True)
    started = perf_counter()
    report = dict(
        status="EXPORTING_BULK_HIERARCHY_PAGES",
        root_qid=events.EVENT_ROOT,
        parameter_version=output.name,
        requested_at_utc=datetime.now(timezone.utc).isoformat(),
        source_version="Live query-service retrieval window; not an atomic dump snapshot",
        complete_services=[],
        pages=[],
        exported_rows=0,
        parameter_table_usable=False,
        filter_started=False,
        code_sha256=digest(Path(__file__)),
    )

    def save():
        report["hierarchy_elapsed_seconds"] = perf_counter() - started
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    save()
    with sqlite3.connect(output / "hierarchy.sqlite") as db:
        create_edge_table(db)
        try:
            for url in SERVICES:
                after = None
                while True:
                    page_started = perf_counter()
                    data, source = events.cached_json(
                        store, url, {"query": bulk_page_query(after), "format": "json"}
                    )
                    links = page_links(data, after)
                    db.executemany(
                        "INSERT INTO hierarchy_edges VALUES(?,?,?,?,?,?,?)",
                        [
                            (
                                statement_key(r["source_record_id"]),
                                r["subject_qid"],
                                r["object_qid"],
                                r["rank"],
                                r["source_record_id"],
                                url,
                                source["retrieved_at"],
                            )
                            for r in links
                        ],
                    )
                    db.commit()
                    terminal = len(links) < PAGE_SIZE
                    report["pages"].append(
                        dict(
                            service=url,
                            cursor=after,
                            terminal=terminal,
                            rows=len(links),
                            elapsed_seconds=perf_counter() - page_started,
                            source=source,
                        )
                    )
                    report["exported_rows"] += len(links)
                    save()
                    LOG.info(
                        "Exported %s rows; service terminal=%s",
                        report["exported_rows"],
                        terminal,
                    )
                    if terminal:
                        report["complete_services"].append(url)
                        break
                    after = links[-1]["source_record_id"]
            report["parameter_rows"] = export_parameters(
                db, output, set(report["complete_services"]) == set(SERVICES)
            )
            report.update(
                status="COMPLETE_EVENT_HIERARCHY_PARAMETERS",
                parameter_table_usable=True,
            )
        except (SourceException, KeyError, ValueError, sqlite3.Error) as exc:
            report.update(
                status="BLOCKED_BULK_HIERARCHY_PARAMETERS",
                exception=getattr(exc, "case", {"reason": str(exc)}),
            )
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    save()
    if report["parameter_table_usable"] and candidates is not None:
        # Record the hierarchy duration before starting the separate timed filter.
        report["filter_started"] = True
        save()
        return dict(
            hierarchy=report,
            filter=filter_candidates(
                output, candidates, store.parent / "wikidata_current_event_cache"
            ),
        )
    return dict(hierarchy=report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    answer = run(args.store, args.output, args.candidates)
    print(
        json.dumps(
            {
                k: {
                    n: v
                    for n, v in r.items()
                    if n not in {"pages", "outputs", "source_receipts"}
                }
                for k, r in answer.items()
            }
        )
    )
    raise SystemExit(
        1 if any(r["status"].startswith("BLOCKED") for r in answer.values()) else 0
    )

"""Current Event-class catalog; population S2T 7, latest hierarchy exception.

Walk native P279 links backwards from the approved root on both query graphs.
This avoids classifying millions of candidate items one at a time. Only
non-deprecated links expand the catalog; untouched responses retain all ranks.
The catalog alone neither discovers Event instances nor populates model rows.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.event_candidate_check import incoming_links
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def reverse_query(parents: list[str], prop: str, after: str | None = None) -> str:
    """Native statements, all ranks, bounded pages; never use truthy P279.

    Reuse existing QID/batch/cursor checks. A page limit is transport only;
    every terminal page on both graphs is required before marking a batch done.
    """
    events.class_edges_query(parents, prop)
    events.incoming_page_query(parents[0], after, 5000)
    values = " ".join(f"wd:{qid}" for qid in parents)
    cursor = f"FILTER(STR(?statement) > {json.dumps(after)})" if after else ""
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?subject ?parent ?property ?statement ?rank WHERE {{
 VALUES ?parent {{ {values} }}
 ?statement ps:{prop} ?parent ; wikibase:rank ?rank .
 ?subject p:{prop} ?statement .
 BIND(wd:{prop} AS ?property)
 FILTER(STRSTARTS(STR(?subject), "http://www.wikidata.org/entity/Q"))
 {cursor}
}}
ORDER BY STR(?statement)
LIMIT 5000
"""


def reverse_pages(store: Path, url: str, parents: list[str], prop: str):
    """Verify each page before yielding any rows or advancing its cursor."""
    after = None
    while True:
        data, source = events.cached_json(
            store, url, {"query": reverse_query(parents, prop, after), "format": "json"}
        )
        links = []
        for row in data["results"]["bindings"]:
            parent = row["parent"]["value"]
            if parent not in {f"http://www.wikidata.org/entity/{p}" for p in parents}:
                raise SourceException("Unexpected class parent", source=source)
            link = incoming_links(
                {"results": {"bindings": [row]}}, parent.rsplit("/", 1)[-1]
            )[0]
            if link["source_predicate"] != f"wd:{prop}":
                raise SourceException("Unexpected class property", source=source)
            links.append(link)
        ids = [row["source_record_id"] for row in links]
        if (
            len(ids) > 5000
            or ids != sorted(set(ids))
            or (after is not None and any(sid <= after for sid in ids))
        ):
            raise SourceException("Incomplete or unordered class page", source=source)
        terminal = len(ids) < 5000
        yield links, dict(
            source=source, parents=parents, cursor=after, terminal=terminal
        )
        if terminal:
            return
        after = ids[-1]


def run(prior: Path, store: Path, output: Path) -> dict:
    """Compute the rank-filtered closure across both graphs, without a depth cap.

    The explicit frontier permits paths whose successive statements reside on
    different services. Independent recursive queries on each graph would miss
    such paths. A class is complete only after both graphs' page chains finish.
    """
    if output.exists() or any(
        not p.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs")
        for p in (store, output)
    ):
        raise ValueError("Use a new approved pipeline output directory")
    check = read_json(prior / "verification.json")
    report = read_json(prior / "report.json")
    if (
        check["status"] != "VERIFIED_CLASSIFICATION_FIRST_BOUNDED_TEST"
        or digest(prior / "report.json") != check["report_sha256"]
    ):
        raise ValueError("Expected verified classification-first test")
    for name, sha in report["outputs"].items():
        if digest(prior / name) != sha:
            raise ValueError(f"Prior output changed: {name}")
    output.mkdir(parents=True)
    classes, completed, edges = {events.EVENT_ROOT}, set(), {}
    result = dict(
        status="RETRIEVING_CURRENT_EVENT_CLASSES",
        root=events.EVENT_ROOT,
        scope="BOTH_CURRENT_QUERY_GRAPHS_P279_CLOSURE",
        queries=[],
        event_rows_written=0,
        events_complete=False,
        final_graph_written=False,
        inputs={
            str(prior / "report.json"): digest(prior / "report.json"),
            str(prior / "verification.json"): digest(prior / "verification.json"),
        },
        code_sha256=digest(Path(__file__)),
    )

    def save() -> None:
        result.update(class_count=len(classes), completed_classes=len(completed))
        (output / "catalog.json").write_text(
            json.dumps(
                dict(
                    classes=sorted(classes),
                    completed=sorted(completed),
                    edges=list(edges.values()),
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        (output / "report.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

    save()
    try:
        while classes - completed:
            batch = sorted(classes - completed, key=lambda q: int(q[1:]))[:10]
            for url in (events.QUERY_URL, events.SCHOLARLY_QUERY_URL):
                for links, receipt in reverse_pages(store, url, batch, "P279"):
                    result["queries"].append(receipt)
                    for link in links:
                        key = link["source_record_id"]
                        if key in edges and edges[key] != link:
                            raise SourceException(
                                "Conflicting class statement", statement=key
                            )
                        edges[key] = link
                        if link["rank"] != "deprecated":
                            classes.add(link["subject_qid"])
                    save()
            completed.update(batch)
            save()
            LOG.info("Event classes=%s; fully checked=%s", len(classes), len(completed))
        result["status"] = "CURRENT_EVENT_CLASS_CATALOG_COMPLETE_FOR_QUERY_GRAPHS"
    except SourceException as exc:
        result.update(status="BLOCKED_CURRENT_EVENT_CLASS_CATALOG", exception=exc.case)
        LOG.error("Stopped: %s", exc.case["reason"])
    except (KeyError, TypeError, ValueError) as exc:
        result.update(
            status="BLOCKED_CURRENT_EVENT_CLASS_CATALOG",
            exception=dict(reason="Malformed class response", error=str(exc)),
        )
        LOG.error("Stopped: malformed class response")
    save()
    result["outputs"] = {"catalog.json": digest(output / "catalog.json")}
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prior", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(args.prior, args.store, args.output)
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"queries", "inputs"}})
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

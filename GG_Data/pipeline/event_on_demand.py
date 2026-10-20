"""Candidate-only Event classification; population S2T section 7.

Read current P31 for our verified candidate IDs. Fetch P279 only when a
candidate needs it; reuse complete class answers and saved positive paths.
No full hierarchy enumeration, Daniel extraction or Event population occurs.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from GG_Data.pipeline import events
from GG_Data.pipeline.event_candidate_check import incoming_links, statement_key
from GG_Data.pipeline.event_instance_candidates import candidate_universe
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def known_path(qid: str, parents: dict[str, list[dict]]) -> list[dict] | None:
    """An incomplete saved graph may prove a positive, never a negative."""
    pending, visited = [(qid, [])], set()
    while pending:
        current, path = pending.pop()
        if current == events.EVENT_ROOT:
            return path
        if current in visited:
            continue
        visited.add(current)
        pending.extend(
            (edge["parent"], path + [edge])
            for edge in parents.get(current, [])
            if edge["rank"] != "deprecated"
        )
    return None


def class_answers(data: dict, batch: list[str], prop: str) -> tuple[dict, set[str]]:
    """Validate complete direct answers, including explicit missing-item flags."""
    target, seen, present = {qid: {} for qid in batch}, set(), set()
    for row in data["results"]["bindings"]:
        uri = row["item"]["value"]
        if uri not in {f"http://www.wikidata.org/entity/{q}" for q in batch}:
            raise SourceException("Unexpected class answer item", item=uri)
        qid = uri.rsplit("/", 1)[-1]
        flag = row["present"]["value"]
        if flag not in {"true", "false"} or ("parent" in row and flag != "true"):
            raise SourceException("Unexpected class presence flag", qid=qid)
        seen.add(qid)
        if flag == "true":
            present.add(qid)
        if "parent" not in row:
            if "statement" in row or "rank" in row:
                raise SourceException("Partial class statement", qid=qid)
            continue
        if not re.fullmatch(
            r"http://www.wikidata.org/entity/Q[1-9]\d*", row["parent"]["value"]
        ):
            raise SourceException("Unexpected class parent", qid=qid)
        native = dict(
            row,
            subject=row["item"],
            property={"value": f"http://www.wikidata.org/entity/{prop}"},
        )
        link = incoming_links(
            {"results": {"bindings": [native]}},
            row["parent"]["value"].rsplit("/", 1)[-1],
        )[0]
        key = statement_key(link["source_record_id"])
        edge = dict(parent=link["object_qid"], statement=key, rank=link["rank"])
        if key in target[qid] and target[qid][key] != edge:
            raise SourceException("Conflicting class statement", statement=key)
        target[qid][key] = edge
    if seen != set(batch):
        raise SourceException(
            "Incomplete class batch", missing=sorted(set(batch) - seen)
        )
    return target, present


def fetch_classes(store: Path, batch: list[str], prop: str, receipt) -> dict:
    """Merge both query services; an absent item requires the native API check.

    S2T 7: all ranks remain evidence; only classification ignores deprecated
    links. A source failure or missing native item is never an empty answer.
    """
    query = events.class_edges_query(batch, prop)
    merged, present = {q: {} for q in batch}, set()
    for url in (events.QUERY_URL, events.SCHOLARLY_QUERY_URL):
        data, source = events.cached_json(
            store, url, {"query": query, "format": "json"}
        )
        rows, found = class_answers(data, batch, prop)
        receipt(dict(property=prop, qids=batch, source=source))
        present.update(found)
        for qid, answers in rows.items():
            for key, edge in answers.items():
                if key in merged[qid] and merged[qid][key] != edge:
                    raise SourceException(
                        "Conflicting class statement across graphs", statement=key
                    )
                merged[qid][key] = edge
    for qid in sorted(set(batch) - present):
        record, source = events.current_record(store, qid)
        receipt(dict(property=prop, qids=[qid], native_fallback=True, source=source))
        for link in events.item_links(record):
            if link["source_predicate"] == f"wd:{prop}":
                key = statement_key(link["source_record_id"])
                merged[qid][key] = dict(
                    parent=link["object_qid"],
                    statement=key,
                    rank=link["raw_statement"]["rank"],
                )
    return {qid: list(rows.values()) for qid, rows in merged.items()}


def event_path(qid: str, parents: dict, hints: dict, fetch) -> list[dict] | None:
    """Stop at the first proven root path; exhaust known branches for negatives.

    Complete fetched answers are memoized. A missing node in the partial
    stopped catalog is not a negative: fetch that node on demand instead.
    """
    pending, visited = [(qid, [])], set()
    while pending:
        current, path = pending.pop()
        shortcut = known_path(current, hints)
        if shortcut is not None:
            return path + shortcut
        if current in visited:
            continue
        visited.add(current)
        if current not in parents:
            parents.update(fetch([current], "P279"))
        pending.extend(
            (edge["parent"], path + [edge])
            for edge in parents[current]
            if edge["rank"] != "deprecated"
        )
    return None


def run(
    candidates: Path, measurement: Path, saved_catalog: Path, store: Path, output: Path
) -> dict:
    if output.exists() or any(
        not p.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs")
        for p in (store, output)
    ):
        raise ValueError("Use a new approved pipeline output directory")
    universe = sorted(
        candidate_universe(candidates, measurement), key=lambda q: int(q[1:])
    )
    old = read_json(saved_catalog / "report.json")
    if (
        old["status"] != "STOPPED_FOR_USER_APPROVED_ON_DEMAND_SWITCH"
        or digest(saved_catalog / "catalog.json") != old["outputs"]["catalog.json"]
    ):
        raise ValueError("Expected unchanged stopped catalog")
    for query in old["queries"]:
        source = query["source"]
        if digest(Path(source["cache"]) / "response.json") != source["sha256"]:
            raise ValueError("Saved positive-path source changed")
    hints = {}
    for link in read_json(saved_catalog / "catalog.json")["edges"]:
        if link["rank"] != "deprecated":
            hints.setdefault(link["subject_qid"], []).append(
                dict(
                    parent=link["object_qid"],
                    statement=link["source_record_id"],
                    rank=link["rank"],
                )
            )
    output.mkdir(parents=True)
    parents = {}
    result = dict(
        status="CLASSIFYING_CANDIDATES_ON_DEMAND",
        candidate_count=len(universe),
        candidates_classified=0,
        hierarchy_positive_count=0,
        class_nodes_fetched=0,
        source_answers=0,
        event_rows_written=0,
        events_complete=False,
        classification_complete=False,
        final_graph_written=False,
        code_sha256=digest(Path(__file__)),
        inputs={
            str(p): digest(p)
            for p in (
                candidates / "report.json",
                candidates / "verification.json",
                measurement / "report.json",
                saved_catalog / "report.json",
                saved_catalog / "catalog.json",
            )
        },
    )

    def save():
        result["class_nodes_fetched"] = len(parents)
        (output / "class_parents.json").write_text(
            json.dumps(parents), encoding="utf-8"
        )
        (output / "report.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

    def receipt(row):
        with (output / "source_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        result["source_answers"] += 1
        save()

    def fetch(batch, prop):
        return fetch_classes(store, batch, prop, receipt)

    save()
    try:
        with (output / "classifications.jsonl").open("a", encoding="utf-8") as f:
            for offset in range(0, len(universe), 10):
                batch = universe[offset : offset + 10]
                direct = fetch(batch, "P31")
                for qid in batch:
                    result["current_qid"] = qid
                    save()
                    proof = None
                    for edge in direct[qid]:
                        if edge["rank"] == "deprecated":
                            continue
                        path = event_path(edge["parent"], parents, hints, fetch)
                        if path is not None:
                            proof = dict(P31=edge, P279=path)
                            break
                    f.write(
                        json.dumps(
                            dict(
                                qid=qid,
                                event_hierarchy_match=proof is not None,
                                proof=proof,
                                P31=direct[qid],
                            )
                        )
                        + "\n"
                    )
                    f.flush()
                    result["candidates_classified"] += 1
                    result["hierarchy_positive_count"] += int(proof is not None)
                    save()
                LOG.info(
                    "Candidates classified=%s/%s; positive=%s",
                    result["candidates_classified"],
                    len(universe),
                    result["hierarchy_positive_count"],
                )
        result.update(
            status="ON_DEMAND_CANDIDATE_CLASSIFICATION_COMPLETE",
            classification_complete=True,
        )
    except SourceException as exc:
        result.update(status="BLOCKED_ON_DEMAND_CLASSIFICATION", exception=exc.case)
        LOG.error("Stopped: %s", exc.case["reason"])
    except (KeyError, TypeError, ValueError) as exc:
        result.update(
            status="BLOCKED_ON_DEMAND_CLASSIFICATION",
            exception=dict(reason="Malformed classification input", error=str(exc)),
        )
        LOG.error("Stopped: malformed classification input")
    save()
    result["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidates", "measurement", "saved-catalog", "store", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(
        args.candidates, args.measurement, args.saved_catalog, args.store, args.output
    )
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"inputs", "outputs"}})
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)

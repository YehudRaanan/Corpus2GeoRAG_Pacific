"""Resolve Daniel's source titles through Wikipedia; preserve prior match runs."""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
from prepare_examples import ROOT, sha256

sys.path.insert(0, str(ROOT / "scripts"))
from fetch_wwii_task_force import WIKIPEDIA_API, api  # noqa: E402

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "runs/first_candidates_v0.1.0_20261018"
MATCH_RUN = HERE / "runs/all_types_notebook_v0.1.0_20261018"
LOG = logging.getLogger(__name__)


def resolve_batch(titles: list[str], response: dict[str, Any]) -> list[dict]:
    """Follow only server-supplied normalization and redirects; never guess."""
    query = response["query"]
    aliases = {
        item["from"]: item["to"]
        for group in ("normalized", "redirects")
        for item in query.get(group, [])
    }
    pages = {page["title"]: page for page in query["pages"]}
    rows = []
    for title in titles:
        resolved, chain = title, []
        seen = set()
        while resolved in aliases and resolved not in seen:
            seen.add(resolved)
            target = aliases[resolved]
            chain.append({"from": resolved, "to": target})
            resolved = target
        page = pages.get(resolved, {})
        props = page.get("pageprops", {})
        qid = props.get("wikibase_item")
        if resolved in seen:
            status = "REDIRECT_CYCLE"
        elif "invalid" in page or "missing" in page:
            status = "MISSING_OR_INVALID_PAGE"
        elif not page:
            status = "NO_PAGE_RETURNED"
        elif "disambiguation" in props:
            status = "DISAMBIGUATION"
        elif page.get("ns") != 0:
            status = "NON_ARTICLE"
        elif not qid:
            status = "NO_WIKIDATA_ID"
        elif not re.fullmatch(r"Q[1-9][0-9]*", qid):
            raise ValueError(f"Invalid Wikidata ID: {qid}")
        elif not isinstance(page.get("pageid"), int) or page["pageid"] <= 0:
            raise ValueError(f"Invalid page ID for {title}")
        else:
            status = "RESOLVED"
        rows.append(
            {
                "Source": title,
                "canonical_title": page.get("title", resolved),
                "wikipedia_page_id": page.get("pageid"),
                "wikipedia_url": "https://en.wikipedia.org/wiki/"
                + quote(resolved.replace(" ", "_"), safe=""),
                "wikidata_id_returned": qid,
                "page_qid": qid if status == "RESOLVED" else None,
                "status": status,
                "normalization_and_redirects": chain,
            }
        )
    return rows


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = ROOT / "Data/external/daniel_20261017.parquet"
    previous = BASELINE / "page_context.jsonl.gz"
    graph = MATCH_RUN / "mapped_graph.jsonl.gz"
    saved_qids = ROOT / "Data/external/wwii_task_force/wikidata_qids.txt"
    inputs = [
        raw,
        previous,
        graph,
        saved_qids,
        Path(__file__),
        ROOT / "scripts/fetch_wwii_task_force.py",
    ]
    hashes = {str(p.relative_to(ROOT)): sha256(p) for p in inputs}
    baseline_manifest = json.loads((BASELINE / "run_manifest.json").read_text("utf-8"))
    match_manifest = json.loads((MATCH_RUN / "run_manifest.json").read_text("utf-8"))
    assert (
        hashes[str(raw.relative_to(ROOT))]
        == baseline_manifest["inputs_sha256"][
            str(raw.relative_to(ROOT)).replace("\\", "/")
        ]
    )
    assert sha256(previous) == baseline_manifest["outputs"][previous.name]["sha256"]
    assert sha256(graph) == match_manifest["outputs"][graph.name]["sha256"]
    sources = pd.read_parquet(raw, columns=["Source"])["Source"]
    if sources.isna().any() or not all(isinstance(t, str) and t for t in sources):
        raise ValueError("Missing or invalid Source title")
    counts = Counter(sources)
    titles = sorted(counts)
    with gzip.open(previous, "rt", encoding="utf-8") as stream:
        old = {row["Source"]: row for row in map(json.loads, stream)}
    assert set(old) == set(titles)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    evidence_path = output / "api_responses.jsonl"
    with evidence_path.open("w", encoding="utf-8") as evidence:
        for start in range(0, len(titles), 50):
            batch = titles[start : start + 50]
            params = {
                "action": "query",
                "titles": "|".join(batch),
                "redirects": 1,
                "prop": "pageprops",
                "ppprop": "wikibase_item|disambiguation",
            }
            response = api(WIKIPEDIA_API, params)
            timestamp = datetime.now(timezone.utc).isoformat()
            batch_id = start // 50
            evidence.write(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "retrieved_utc": timestamp,
                        "endpoint": WIKIPEDIA_API,
                        "params": params,
                        "response": response,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            evidence.flush()
            for row in resolve_batch(batch, response):
                prior_qid = old[row["Source"]]["page_qid"]
                row.update(
                    {
                        "retrieved_utc": timestamp,
                        "evidence_batch_id": batch_id,
                        "mentions": counts[row["Source"]],
                        "previous_page_qid": prior_qid,
                    }
                )
                if prior_qid and row["page_qid"] and prior_qid != row["page_qid"]:
                    row.update(status="CONFLICT_WITH_SNAPSHOT", page_qid=None)
                rows.append(row)
            LOG.info("Looked up %d/%d titles", len(rows), len(titles))

    qids = {r["page_qid"] for r in rows if r["page_qid"]}
    neighbours = {qid: set() for qid in qids}
    with gzip.open(graph, "rt", encoding="utf-8") as stream:
        for edge in map(json.loads, stream):
            a, b = edge["subject"], edge["object"]
            if a in neighbours and b != a:
                neighbours[a].add(b)
            if b in neighbours and b != a:
                neighbours[b].add(a)
    snapshot_ids = set(saved_qids.read_text("utf-8").splitlines())
    for row in rows:
        qid = row["page_qid"]
        row["qid_in_saved_wikidata_population"] = qid in snapshot_ids if qid else None
        row["saved_graph_direct_neighbours"] = len(neighbours[qid]) if qid else None

    write_json(output / "page_map.json", rows)
    assert len(rows) == len(titles) and {r["Source"] for r in rows} == set(titles)
    assert sum(r["mentions"] for r in rows) == len(sources)
    assert hashes == {str(p.relative_to(ROOT)): sha256(p) for p in inputs}
    newly_resolved = [r for r in rows if not r["previous_page_qid"] and r["page_qid"]]
    summary = {
        "source_pages": len(rows),
        "input_mentions": len(sources),
        "previously_resolved_pages": sum(bool(r["previous_page_qid"]) for r in rows),
        "statuses": dict(Counter(r["status"] for r in rows)),
        "resolved_mentions": sum(r["mentions"] for r in rows if r["page_qid"]),
        "newly_resolved_pages": len(newly_resolved),
        "newly_resolved_mentions": sum(r["mentions"] for r in newly_resolved),
        "newly_resolved_pages_with_saved_graph_neighbours": sum(
            bool(r["saved_graph_direct_neighbours"]) for r in newly_resolved
        ),
        "resolved_pages_without_saved_graph_neighbours": sum(
            r["saved_graph_direct_neighbours"] == 0 for r in rows if r["page_qid"]
        ),
        "unresolved_sources": [r["Source"] for r in rows if not r["page_qid"]],
        "scope": "Current Wikipedia page identity only; extraction revision is unknown. No entity matching rerun or graph expansion.",
    }
    write_json(output / "summary.json", summary)
    write_json(
        output / "run_manifest.json",
        {
            "status": "COMPLETED",
            "method": "wikipedia-source-title-redirects-v0.1.0",
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "inputs_sha256": hashes,
            "outputs_sha256": {
                name: sha256(output / name)
                for name in ("page_map.json", "summary.json", "api_responses.jsonl")
            },
            "verification": {
                "all_sources_accounted_for": True,
                "inputs_unchanged": True,
            },
        },
    )
    LOG.info("%s", json.dumps(summary))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()

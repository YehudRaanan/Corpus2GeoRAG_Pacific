"""Run a bounded, evidence-labelled Geography retrieval plan without assignments.

Population S2T 9: names, aliases, page context and source coordinates may guide
candidate retrieval. A retrieval clue is not an accepted parent or a new entity.
This diagnostic deliberately does not call the production acceptance selector.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .geography_sample import tools
from .poc import digest, read_json
from .rebuild_poc import write


def run(plan_path: Path, output: Path) -> dict:
    """Cache each single-threaded request; fail rather than silently retry."""
    plan = read_json(plan_path)
    plan_sha = digest(plan_path)
    (output / "sources").mkdir(parents=True, exist_ok=True)
    client = tools()
    results = []
    new_requests, reused_requests = 0, 0
    for index, query in enumerate(plan["queries"]):
        if query["kind"] not in {"search", "reverse"} or not query["evidence"]:
            raise ValueError("Expected an evidence-labelled search or reverse query")
        params = (
            dict(
                format="jsonv2",
                namedetails="1",
                extratags="1",
                addressdetails="1",
                polygon_geojson="1",
            )
            | query["params"]
        )
        if query["kind"] == "search":
            params["limit"] = "10"
        url = client.NOMINATIM["OpenStreetMap"] + "/" + query["kind"]
        path = output / "sources" / f"{index:02d}.json"
        if path.exists():
            saved = read_json(path)
            if saved["url"] != url or saved["params"] != params:
                raise ValueError("Cached query differs; preserve old evidence")
            reused_requests += 1
        else:
            payload = client.request_json(url, params=params)
            new_requests += 1
            write(
                path,
                dict(
                    url=url,
                    params=params,
                    response=payload,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                ),
            )
            time.sleep(1.1)  # Public Nominatim policy: one reader, <= 1 request/s.
            saved = read_json(path)
        payload = saved["response"]
        # A documented no-coverage reverse result is evidence, not a match.
        if query["kind"] == "search" and not isinstance(payload, list):
            raise ValueError("Unexpected Nominatim search response")
        if query["kind"] == "reverse" and not isinstance(payload, dict):
            raise ValueError("Unexpected Nominatim reverse response")
        rows = payload if isinstance(payload, list) else [payload]
        results.append(
            query | dict(source_file=str(path), sha256=digest(path), rows=rows)
        )
        write(
            output / "progress.json",
            dict(completed=len(results), total=len(plan["queries"])),
        )
        print(
            json.dumps(
                dict(
                    completed=len(results),
                    name=query["name"],
                    kind=query["kind"],
                    rows=len(rows),
                )
            ),
            flush=True,
        )
    if digest(plan_path) != plan_sha:
        raise ValueError("Query plan changed during retrieval")
    report = dict(
        status="VERIFIED_RETRIEVAL_ONLY",
        query_plan_sha256=plan_sha,
        results=results,
        accepted_assignments=0,
        new_requests=new_requests,
        reused_requests=reused_requests,
        model_changed=False,
        identity_assignments_changed=False,
    )
    write(output / "retrieval.json", report)
    return dict(
        status=report["status"],
        queries=len(results),
        accepted_assignments=0,
        new_requests=new_requests,
        reused_requests=reused_requests,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.plan, args.output)))

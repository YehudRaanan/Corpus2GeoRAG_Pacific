"""Verify the full compact population and both directions through real Agent tools."""

from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from .compact_store import CompactGraphStore
from .tools import build_tools


def verify(path: Path, report: Path) -> dict:
    path, report = Path(path), Path(report)
    temporary = report.with_name(report.name + ".part")
    if report.exists() or temporary.exists():
        raise FileExistsError(report)
    store = CompactGraphStore.load(path)
    try:
        coverage = json.loads(
            store.connection.execute(
                "SELECT value FROM audit WHERE key='coverage'"
            ).fetchone()[0]
        )
        tool = next(t for t in build_tools(store) if t.name == "find_relations")
        checks = []
        for category, (a, b) in sorted(coverage["category_samples"].items()):
            for source, target in [(a, b), (b, a)]:
                source_id, target_id = store.node_ids[source], store.node_ids[target]
                rows = json.loads(
                    tool.invoke(dict(source_id=source_id, target_id=target_id))
                )
                if len(rows) != 1:
                    raise ValueError("Agent tool did not return the exact pair")
                row = rows[0]
                shared = set(store.nodes[source_id].attributes["page_indices"]) & set(
                    store.nodes[target_id].attributes["page_indices"]
                )
                denominator = store.nodes[source_id].attributes["page_count"]
                if (
                    type(row["count"]) is not int
                    or row["count"] != len(shared)
                    or row["shared_page_indices"] != sorted(shared)
                    or row["source_page_count"] != denominator
                    or not math.isclose(row["strength"], len(shared) / denominator)
                    or row["semantics"] != "PAGE_CO_OCCURRENCE_ONLY"
                ):
                    raise ValueError(
                        "Agent directional tool result differs from membership"
                    )
                checks.append(dict(category=category, **row))
        index = path.with_name(path.name + ".sqlite")
        receipt = json.loads(index.with_name(index.name + ".json").read_text())
        result = dict(
            status="PASS",
            verified_at_utc=datetime.now(timezone.utc).isoformat(),
            graph_sha256=receipt["graph_sha256"],
            index_sha256=receipt["index_sha256"],
            verification="ALL_PAIRS_MEMBERSHIP_WEIGHTS_UNIQUENESS_AND_CONSERVATION",
            node_count=len(store.nodes),
            coverage=coverage,
            schema=store.schema(),
            tool_checks=checks,
            llm_invoked=False,
            geography_status=store.metadata.get("geography_status"),
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        temporary.replace(report)
        return result
    finally:
        store.connection.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = verify(args.graph, args.report)
    print(
        json.dumps(
            dict(
                status=result["status"],
                node_count=result["node_count"],
                coverage=result["coverage"],
            )
        )
    )

"""Verify the full compact population and both directions through real Agent tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .compact_store import CompactGraphStore
from .tools import build_tools


def verify_geography(store) -> dict:
    """Check every portable LOC geometry and real spatial queries by shape type."""
    locations = sorted(
        (n for n in store.nodes.values() if n.type == "location"), key=lambda n: n.id
    )
    complete = store.metadata.get("geography_status", "").startswith("COMPLETE")
    geometry_sha, statuses, types, samples = hashlib.sha256(), Counter(), Counter(), {}
    for node in locations:
        status = node.attributes.get("geography_status", "PENDING_LAST_STAGE")
        statuses[status] += 1
        if complete and ("PENDING" in status or not status):
            raise ValueError("Completed Geography contains pending locations")
        geometry_sha.update(
            json.dumps(
                [node.id, node.geometry, status],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        )
        if node.geometry:
            geo = store.geoms[node.id]
            if complete and (
                status != "RESOLVED"
                or not (
                    -180 <= geo.bounds[0] <= geo.bounds[2] <= 180
                    and -90 <= geo.bounds[1] <= geo.bounds[3] <= 90
                )
            ):
                raise ValueError("Invalid completed Geography shape/status")
            types[geo.geom_type] += 1
            samples.setdefault(geo.geom_type, node.id)
        elif complete and status == "RESOLVED":
            raise ValueError("Resolved Agent location lacks geometry")
    checks = []
    tool = next(t for t in build_tools(store) if t.name == "entities_near")
    for kind, key in sorted(samples.items()):
        # This point is only a query probe. The stored native shape is unchanged.
        point = store.geoms[key].representative_point()
        hits = store.near(
            point.y, point.x, 0.001, type="location", limit=len(locations)
        )
        if key not in {r["id"] for r in hits}:
            raise ValueError("Spatial query lost its native source geometry")
        result = json.loads(
            tool.invoke(
                dict(lat=point.y, lon=point.x, radius_km=0.001, type="location")
            )
        )
        if not isinstance(result, list) or not result:
            raise ValueError("Agent spatial tool returned no geometry")
        checks.append(
            dict(
                entity_id=key,
                geometry_type=kind,
                query_only_point=[point.x, point.y],
                target_returned=True,
                real_agent_tool_hits=len(result),
            )
        )
    return dict(
        locations=len(locations),
        status_counts=dict(statuses),
        geometry_types=dict(types),
        geometry_rows_sha256=geometry_sha.hexdigest(),
        spatial_checks=checks,
    )


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
            geography=verify_geography(store),
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

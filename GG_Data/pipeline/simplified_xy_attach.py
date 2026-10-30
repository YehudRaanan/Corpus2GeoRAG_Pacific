"""Attach a verified arbitrary-point overlay without changing core edge bytes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from Agent.geo_agent.compact_format import COLUMNS, HEADER

from .poc import digest, read_json
from .simplified_agent import write_object
from .simplified_xy import METHOD, valid_xy

STATUS = "PARTIAL_ARBITRARY_SOURCE_POINTS"
PROOF = "ALL_PAIRS_MEMBERSHIP_WEIGHTS_UNIQUENESS_AND_CONSERVATION"


def encoded(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def update_node(node: dict, row: dict) -> dict:
    """Change only geometry and the two explicit geography attributes."""
    kind = {"location": "LOC", "event": "event"}[node["type"]]
    if row["name"] != node["name"] or row["type"] != kind:
        raise ValueError("Overlay name/type differs from exact core identity")
    if node.get("geometry") is not None or "xy_source" in node["attributes"]:
        raise ValueError("Core already has geometry or an XY attachment")
    geometry = row.get("geometry")
    if row.get("identity_verified") is not False:
        raise ValueError("Overlay must not claim verified identity")
    if geometry is not None:
        xy = geometry.get("coordinates")
        if (
            geometry.get("type") != "Point"
            or not valid_xy(xy)
            or len(xy) != 2
            or xy != [row.get("x"), row.get("y")]
            or row.get("crs") != "EPSG:4326"
            or row.get("selection_method") != METHOD
            or row.get("status") != "SOURCE_POINT_SELECTED_ARBITRARILY"
        ):
            raise ValueError("Invalid arbitrary Earth point")
    elif not row.get("status", "").startswith("NO_"):
        raise ValueError("Missing point requires explicit no-source status")
    provenance = {
        k: v
        for k, v in row.items()
        if k not in {"entity_id", "name", "type", "geometry"}
    }
    return dict(
        node,
        geometry=geometry,
        attributes=dict(
            node["attributes"], geography_status=row["status"], xy_source=provenance
        ),
    )


def attach(graph: Path, acceptance: Path, overlay_dir: Path, output: Path) -> dict:
    """Create a new graph; full real-Agent acceptance is a separate required gate."""
    graph, acceptance, overlay_dir, output = map(
        Path, (graph, acceptance, overlay_dir, output)
    )
    if output.exists():
        raise FileExistsError(output)
    proof = read_json(acceptance)
    graph_sha = digest(graph)
    if (
        proof.get("status") != "PASS"
        or proof.get("verification") != PROOF
        or proof.get("graph_sha256") != graph_sha
        or len(proof.get("coverage", {}).get("pair_rows_sha256", "")) != 64
    ):
        raise ValueError("Core graph lacks matching full Agent acceptance")
    manifest_path = overlay_dir / "manifest.json"
    manifest = read_json(manifest_path)
    overlay_path = overlay_dir / "xy_overlay.json.gz"
    overlay_sha, manifest_sha = digest(overlay_path), digest(manifest_path)
    verified = read_json(overlay_dir / "verification.json")
    if (
        manifest.get("outputs", {}).get(overlay_path.name) != overlay_sha
        or verified.get("status")
        != "VERIFIED_LOCAL_OVERLAY_IDS_SOURCE_HASHES_AND_PRESERVED_ROWS"
        or verified.get("overlay_sha256") != overlay_sha
        or verified.get("manifest_sha256") != manifest_sha
    ):
        raise ValueError("Overlay source binding differs from verification")
    rows = read_json(overlay_path)
    by_id = {row["entity_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("Duplicate overlay identity")
    output.mkdir(parents=True)
    target = output / "agent_graph.json.gz"
    temporary = target.with_name(target.name + ".part")
    counts, seen = Counter(), set()
    edge_sha, line_count, final_bytes = hashlib.sha256(), 0, b""
    with gzip.open(graph, "rb") as source, gzip.open(
        temporary, "xb", compresslevel=1
    ) as destination:
        header = source.readline()
        newline = b"\r\n" if header.endswith(b"\r\n") else b"\n"
        if header != HEADER.encode().replace(b"\n", newline):
            raise ValueError("Unsupported compact graph header")
        line = source.readline()
        if not line.startswith(b'"metadata":') or not line.endswith(b"," + newline):
            raise ValueError("Invalid compact metadata framing")
        metadata = json.loads(line[len(b'"metadata":') : -len(newline) - 1])
        if (
            metadata.get("edge_columns") != COLUMNS
            or metadata.get("node_count") != proof["node_count"]
            or metadata.get("pair_count") != proof["coverage"]["pair_count"]
            or metadata.get("model_manifest_sha256")
            != manifest.get("core_model_manifest_sha256")
        ):
            raise ValueError("Core/overlay population binding differs")
        if source.readline() != b'"nodes":[' + newline:
            raise ValueError("Invalid node framing")
        binding = dict(
            geography_status=STATUS,
            xy_overlay_sha256=overlay_sha,
            xy_overlay_manifest_sha256=manifest_sha,
            xy_core_graph_sha256=graph_sha,
            xy_identity_verified=False,
            xy_scope="EXACT_ID_JOIN_LOC_AND_EVENTS; MISSING_POINTS_EXPLICIT",
            xy_coverage=manifest.get("counts", {}),
        )
        destination.write(header)
        destination.write(
            b'"metadata":' + encoded(dict(metadata, **binding)) + b"," + newline
        )
        destination.write(b'"nodes":[' + newline)
        for index in range(metadata["node_count"]):
            line = source.readline()
            suffix = b"," + newline if index + 1 < metadata["node_count"] else newline
            if not line.endswith(suffix):
                raise ValueError("Invalid core node framing")
            node = json.loads(line[: -len(suffix)])
            if node["id"] in seen:
                raise ValueError("Duplicate core node identity")
            seen.add(node["id"])
            if node["type"] in {"location", "event"}:
                if node["id"] not in by_id:
                    raise ValueError("Core location/Event missing from overlay")
                updated = update_node(node, by_id.pop(node["id"]))
                counts[node["type"], updated["attributes"]["geography_status"]] += 1
                destination.write(encoded(updated) + suffix)
            else:
                destination.write(line)
        if by_id:
            raise ValueError("Foreign overlay identity absent from core population")
        if (
            source.readline() != b"]," + newline
            or source.readline() != b'"edges":[' + newline
        ):
            raise ValueError("Invalid edge array framing")
        destination.write(b"]," + newline + b'"edges":[' + newline)
        # The accepted graph hash binds framing and canonical pair proof. Copy
        # every decompressed edge byte, without parsing or re-encoding pairs.
        edge_sha.update(newline)
        while chunk := source.read(4 * 1024 * 1024):
            destination.write(chunk)
            edge_sha.update(chunk)
            line_count += chunk.count(b"\n")
            final_bytes = (final_bytes + chunk)[-len(newline) - 2 :]
        if line_count != metadata["pair_count"] + 1 or final_bytes != b"]}" + newline:
            raise ValueError("Copied edge tail count/end differs from accepted graph")
    temporary.replace(target)
    result = dict(
        status="ATTACHED_PENDING_FULL_AGENT_ACCEPTANCE",
        geography_status=STATUS,
        node_count=metadata["node_count"],
        pair_count=metadata["pair_count"],
        pair_rows_sha256=proof["coverage"]["pair_rows_sha256"],
        edge_tail_sha256=edge_sha.hexdigest(),
        edge_bytes_preserved=True,
        counts={
            kind: {status: count for (k, status), count in counts.items() if k == kind}
            for kind in sorted({k for k, _ in counts})
        },
        inputs={
            str(graph): graph_sha,
            str(acceptance): digest(acceptance),
            str(manifest_path): manifest_sha,
            str(overlay_path): overlay_sha,
            str(overlay_dir / "verification.json"): digest(
                overlay_dir / "verification.json"
            ),
        },
        code_sha256=digest(Path(__file__)),
        outputs={target.name: digest(target)},
        caveat="Arbitrary source points do not establish name identity, historical extent, or physical Event location.",
    )
    write_object(output / "manifest.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["graph", "acceptance", "overlay", "output"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    attach(args.graph, args.acceptance, args.overlay, args.output)

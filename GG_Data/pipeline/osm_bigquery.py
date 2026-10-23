"""S2T 9.7: cached, exact-QID OSM geometries from the approved public table.

This replaces bulk Overpass retrieval only. Native OSM geometry and tags feed
the existing ranker; no new identity, geometry or acceptance rule is added.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from shapely import from_wkb
from shapely.geometry import mapping

from .poc import ROOT, digest, read_json
from .rebuild_poc import write

TABLE = "bigquery-public-data.geo_openstreetmap.planet_features"
NAME = "osm_bigquery_candidates.json"


def project(row: dict, qids: set[str], receipt: str) -> dict:
    """Preserve GDAL layer/object IDs and source geometry, not tag centres."""
    tags = {t["key"]: t["value"] for t in row["all_tags"]}
    if tags.get("wikidata") not in qids:
        raise ValueError("OSM BigQuery returned an out-of-scope Wikidata ID")
    layer = row["feature_type"]
    number = row.get("osm_id")
    if layer == "points":
        kind = "node"
    elif layer == "lines":
        kind = "way"
    elif layer == "multipolygons" and row.get("osm_way_id") is not None:
        kind, number = "way", row["osm_way_id"]
    elif layer in {"multipolygons", "multilinestrings", "other_relations"}:
        kind = "relation"
    else:
        raise ValueError(f"Unknown native OSM layer: {layer}")
    if not re.fullmatch(r"[1-9]\d*", str(number)):
        raise ValueError("Missing or invalid native OSM object ID")
    geometry = from_wkb(bytes.fromhex(row["geometry_wkb"]))
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"Invalid native OSM geometry: {kind}:{number}")
    aliases = [
        part
        for key, value in tags.items()
        if key in {"name", "alt_name", "old_name", "official_name", "short_name"}
        or key.startswith("name:")
        for part in value.split(";")
    ]
    return dict(
        source="OpenStreetMap",
        source_id=f"{kind}:{number}",
        qid=tags["wikidata"],
        name=tags.get("name", ""),
        aliases=aliases,
        feature_code=None,
        feature_class=None,
        address_type=None,
        parents=[
            v
            for k, v in tags.items()
            if k in {"addr:country", "addr:state", "addr:city"}
        ],
        tags=tags,
        geometry=mapping(geometry),
        receipt=receipt,
        osm_version=row.get("osm_version"),
        osm_timestamp=row.get("osm_timestamp"),
    )


def load(path: Path, qids: list[str]) -> list[dict]:
    """A complete, checksummed query receipt is required before cache reuse."""
    saved = read_json(path)
    if saved["qids"] != sorted(set(qids)):
        raise ValueError("OSM BigQuery cache has different targets")
    for name, sha in saved["inputs"].items():
        if digest(Path(name)) != sha:
            raise ValueError(f"Changed OSM BigQuery receipt: {name}")
    if any(c["qid"] not in qids for c in saved["candidates"]):
        raise ValueError("OSM BigQuery candidate is outside the target population")
    return saved["candidates"]


def retrieve(base: Path) -> dict:
    """Run one cloud query for the full target population and retain receipts."""
    output = base / "geography_retrieval/sources" / NAME
    qids = sorted(
        {
            p["wikidata_id"]
            for p in read_json(base / "geography_retrieval/sample.json")
            if p["wikidata_id"]
        }
    )
    if output.exists():
        load(output, qids)
        return read_json(output)
    if any(not re.fullmatch(r"Q[1-9]\d*", q) for q in qids):
        raise ValueError("Invalid OSM target Wikidata ID")
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from bigquery_direct_wikidata import BigQueryData
    finally:
        sys.path.pop(0)
    store = output.parent / "osm_bigquery_cache"
    reference = read_json(base / "matching/reference_manifest.json")
    client = BigQueryData(reference["project"], store, table=TABLE)
    selected = ",".join(f"'{q}'" for q in qids)
    sql = f"""SELECT feature_type, osm_id, osm_way_id, osm_version,
 osm_timestamp, all_tags, TO_HEX(ST_ASBINARY(geometry)) geometry_wkb
 FROM {client.source}
 WHERE EXISTS(SELECT 1 FROM UNNEST(all_tags) t
 WHERE t.key='wikidata' AND t.value IN ({selected}))"""
    rows = client.query(sql)
    receipt = store / (hashlib.sha256(sql.encode()).hexdigest() + ".json.gz")
    candidates = [project(row, set(qids), str(receipt)) for row in rows]
    report = dict(
        status="COMPLETE_OSM_BIGQUERY_NATIVE_GEOMETRIES",
        table=TABLE,
        qids=qids,
        candidates=candidates,
        query_evidence=client.requests,
        snapshot=client.snapshot,
        inputs={str(p): digest(p) for p in (receipt, store / "table_snapshot.json")},
        ranking_changed=False,
    )
    write(output, report)
    return report

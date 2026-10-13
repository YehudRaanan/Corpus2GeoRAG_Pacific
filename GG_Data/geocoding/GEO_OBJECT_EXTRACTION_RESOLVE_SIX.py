"""Resolve the six places left open by the first 50-place geometry run."""

from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import ijson
import pandas as pd
from shapely.geometry import Point, shape

from GEO_OBJECT_EXTRACTION_POC import USER_AGENT

ROOT = Path(__file__).parents[2]
GRAPH = (
    ROOT
    / "GG_Data"
    / "agent_export"
    / "outputs"
    / "wwii_agent_graph_draft_v0.1.0.json"
)
HERE = Path(__file__).parent
CACHE = HERE / "cache"
BASE_AUDIT = HERE / "GEO_OBJECT_EXTRACTION_FIRST_50_AUDIT.json"
BASE_GEOMETRIES = HERE / "GEO_OBJECT_EXTRACTION_FIRST_50.parquet"
RESULT = HERE / "GEO_OBJECT_EXTRACTION_UNRESOLVED_SIX_RESULT.json"
V2_AUDIT = HERE / "GEO_OBJECT_EXTRACTION_FIRST_50_V2_AUDIT.json"
V2_SUMMARY = HERE / "GEO_OBJECT_EXTRACTION_FIRST_50_V2_SUMMARY.csv"
V2_GEOMETRIES = HERE / "GEO_OBJECT_EXTRACTION_FIRST_50_V2.parquet"
POLICY_VERSION = "geo-object-selection-v0.5.0"

AIRPORT_RULES = {
    "Q17607": {
        "query": "Bathurst Island Airport, Northern Territory, Australia",
    },
    "Q17619": {
        "query": "Port Keats Aerodrome, Northern Territory, Australia",
    },
}

GEONAMES_RULES = {
    "Q10094": {
        "country": "IN",
        "feature_codes": {"HLLS"},
        "admin1": "25",
        "reason": "exact aliases, mountain-range type, and Tamil Nadu parent",
    },
    "Q63252": {
        "country": "JP",
        "feature_codes": {"PPLX"},
        "admin2": "1856152",
        "reason": "exact alias, populated-place section type, and Nagasaki parent",
    },
    "Q101081": {
        "country": "FR",
        "feature_codes": {"RGN"},
        "source_id": "2985246",
        "reason": "exact Wikidata-to-GeoNames identity link and region type",
    },
    "Q151198": {
        "country": "DE",
        "feature_codes": {"HSTS"},
        "reason": "exact full name and historical-site type",
    },
}


def request_json(url: str, params: dict[str, str] | None = None) -> Any:
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def input_nodes(qids: set[str]) -> dict[str, dict[str, Any]]:
    nodes = {}
    with GRAPH.open("rb") as stream:
        for node in ijson.items(stream, "nodes.item"):
            if node.get("id") in qids:
                nodes[node["id"]] = node
                if len(nodes) == len(qids):
                    break
    return nodes


def osm_tags(osm_type: str, osm_id: int) -> dict[str, str]:
    api_type = {"N": "node", "W": "way", "R": "relation"}[osm_type]
    payload = request_json(
        f"https://api.openstreetmap.org/api/0.6/{api_type}/{osm_id}.json"
    )
    return payload["elements"][0].get("tags", {})


def resolve_airports(nodes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    results = {}
    for qid, rule in AIRPORT_RULES.items():
        aliases = {str(alias).upper() for alias in nodes[qid].get("aliases", [])}
        rows = request_json(
            "https://nominatim.openstreetmap.org/search",
            {
                "q": rule["query"],
                "format": "jsonv2",
                "polygon_geojson": "1",
                "addressdetails": "1",
                "limit": "10",
            },
        )
        candidates = []
        for row in rows:
            if row.get("category") != "aeroway" or row.get("type") != "aerodrome":
                continue
            prefix = {"node": "N", "way": "W", "relation": "R"}[row["osm_type"]]
            tags = osm_tags(prefix, row["osm_id"])
            if tags.get("iata") not in aliases or tags.get("icao") not in aliases:
                continue
            geometry = shape(row["geojson"])
            if geometry.is_empty or not geometry.is_valid:
                continue
            candidates.append((row, tags, geometry))
        if len(candidates) != 1:
            raise RuntimeError(f"{qid}: expected one airport match, found {len(candidates)}")
        row, tags, geometry = candidates[0]
        results[qid] = {
            "qid": qid,
            "name": nodes[qid]["name"],
            "source_dataset": "OpenStreetMap",
            "source_object_id": f"W{row['osm_id']}",
            "source_url": f"https://www.openstreetmap.org/way/{row['osm_id']}",
            "match_method": "EXACT_IATA_ICAO_AND_TYPE",
            "decision_reason": (
                f"one aerodrome matched IATA {tags['iata']} and ICAO {tags['icao']}"
            ),
            "evidence": {
                "query": rule["query"],
                "iata": tags["iata"],
                "icao": tags["icao"],
                "source_name": tags.get("name"),
            },
            "geometry": geometry,
        }
        time.sleep(1.1)
    return results


def ensure_geonames(country: str) -> Path:
    folder = CACHE / "geonames"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{country}.zip"
    if path.exists():
        return path
    request = urllib.request.Request(
        f"https://download.geonames.org/export/dump/{country}.zip",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=240) as response:
        path.write_bytes(response.read())
    return path


def geonames_rows(country: str) -> list[dict[str, str]]:
    rows = []
    with zipfile.ZipFile(ensure_geonames(country)) as archive:
        with archive.open(f"{country}.txt") as stream:
            for raw in stream:
                fields = raw.decode("utf-8").rstrip("\n").split("\t")
                rows.append(
                    {
                        "id": fields[0],
                        "name": fields[1],
                        "ascii_name": fields[2],
                        "alternate_names": fields[3],
                        "latitude": fields[4],
                        "longitude": fields[5],
                        "feature_code": fields[7],
                        "admin1": fields[10],
                        "admin2": fields[11],
                    }
                )
    return rows


def resolve_geonames(nodes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    country_rows = {
        country: geonames_rows(country)
        for country in {rule["country"] for rule in GEONAMES_RULES.values()}
    }
    results = {}
    for qid, rule in GEONAMES_RULES.items():
        node = nodes[qid]
        linked_ids = []
        if rule.get("source_id"):
            entity = request_json(
                f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
            )["entities"][qid]
            linked_ids = [
                claim["mainsnak"]["datavalue"]["value"]
                for claim in entity.get("claims", {}).get("P1566", [])
                if "datavalue" in claim["mainsnak"]
            ]
            if rule["source_id"] not in linked_ids:
                raise RuntimeError(f"{qid}: expected GeoNames identity link is missing")
        input_names = {
            str(name).casefold() for name in [node["name"], *node.get("aliases", [])]
        }
        matches = []
        for row in country_rows[rule["country"]]:
            source_names = {
                row["name"].casefold(),
                row["ascii_name"].casefold(),
                *(name.casefold() for name in row["alternate_names"].split(",") if name),
            }
            if not input_names & source_names:
                continue
            if row["feature_code"] not in rule["feature_codes"]:
                continue
            if rule.get("admin1") and row["admin1"] != rule["admin1"]:
                continue
            if rule.get("admin2") and row["admin2"] != rule["admin2"]:
                continue
            if rule.get("source_id") and row["id"] != rule["source_id"]:
                continue
            matches.append(row)
        if len(matches) != 1:
            raise RuntimeError(f"{qid}: expected one GeoNames match, found {len(matches)}")
        row = matches[0]
        results[qid] = {
            "qid": qid,
            "name": node["name"],
            "source_dataset": "GeoNames",
            "source_object_id": row["id"],
            "source_url": f"https://www.geonames.org/{row['id']}",
            "match_method": "EXACT_NAME_ALIAS_TYPE_AND_CONTEXT",
            "decision_reason": "one GeoNames record matched " + rule["reason"],
            "evidence": {
                "source_name": row["name"],
                "feature_code": row["feature_code"],
                "admin1": row["admin1"],
                "admin2": row["admin2"],
                "wikidata_p1566": linked_ids,
            },
            "geometry": Point(float(row["longitude"]), float(row["latitude"])),
        }
    return results


def write_outputs(resolutions: dict[str, dict[str, Any]]) -> None:
    base = json.loads(BASE_AUDIT.read_text(encoding="utf-8"))
    base_rows = {row["qid"]: row for row in base["results"]}
    generated_at = datetime.now(timezone.utc).isoformat()

    audit_results = []
    geometry_records = []
    geometries = []
    for qid, resolution in resolutions.items():
        geometry = resolution["geometry"]
        audit_results.append(
            {
                key: value
                for key, value in resolution.items()
                if key != "geometry"
            }
            | {
                "selection_date": base_rows[qid]["selection_date"],
                "geometry_type": geometry.geom_type,
                "geometry_valid": geometry.is_valid and not geometry.is_empty,
                "review_status": "ACCEPTED_AUTO",
            }
        )
        geometry_records.append(
            {
                "place_id": qid,
                "name": resolution["name"],
                "place_type": base_rows[qid]["place_type"],
                "selection_date": base_rows[qid]["selection_date"],
                "source_dataset": resolution["source_dataset"],
                "source_object_id": resolution["source_object_id"],
                "source_url": resolution["source_url"],
                "match_method": resolution["match_method"],
                "selection_policy_version": POLICY_VERSION,
                "retrieved_at": generated_at,
                "review_status": "ACCEPTED_AUTO",
                "decision_reason": resolution["decision_reason"],
            }
        )
        geometries.append(geometry)

    RESULT.write_text(
        json.dumps(
            {
                "policy_version": POLICY_VERSION,
                "generated_at": generated_at,
                "summary": {
                    "input_unresolved": len(resolutions),
                    "accepted_auto": len(resolutions),
                    "still_unresolved": 0,
                    "sources": {
                        "OpenStreetMap": sum(
                            row["source_dataset"] == "OpenStreetMap"
                            for row in audit_results
                        ),
                        "GeoNames": sum(
                            row["source_dataset"] == "GeoNames"
                            for row in audit_results
                        ),
                    },
                },
                "results": audit_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fallback = gpd.GeoDataFrame(geometry_records, geometry=geometries, crs=None)
    original = gpd.read_parquet(BASE_GEOMETRIES)
    combined = gpd.GeoDataFrame(
        pd.concat([original, fallback], ignore_index=True), geometry="geometry", crs=None
    ).sort_values("place_id")
    if not combined["place_id"].is_unique:
        raise RuntimeError("The combined geometry table contains duplicate place IDs")
    combined.to_parquet(V2_GEOMETRIES, index=False)

    for row in audit_results:
        target = base_rows[row["qid"]]
        target.update(
            selected_source=row["source_dataset"],
            selected_object_id=row["source_object_id"],
            review_status="ACCEPTED_AUTO",
            decision_reason=row["decision_reason"],
            geometry_valid=True,
            fallback_search=row,
        )
    base["policy_version"] = POLICY_VERSION
    base["generated_at"] = generated_at
    base["summary"]["status_counts"] = {"ACCEPTED_AUTO": 47, "REJECTED_NOT_PLACE": 3}
    base["summary"]["geometry_rows"] = len(combined)
    base["summary"]["fallback_resolved"] = len(resolutions)
    V2_AUDIT.write_text(
        json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fields = [
        "input_rank",
        "qid",
        "name",
        "place_type",
        "selection_date",
        "exact_qid_count",
        "selected_source",
        "selected_object_id",
        "review_status",
        "geometry_valid",
        "decision_reason",
    ]
    with V2_SUMMARY.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(base["results"])


def main() -> None:
    qids = set(AIRPORT_RULES) | set(GEONAMES_RULES)
    nodes = input_nodes(qids)
    if set(nodes) != qids:
        raise RuntimeError("One or more unresolved source nodes are missing")
    resolutions = resolve_airports(nodes) | resolve_geonames(nodes)
    write_outputs(resolutions)
    print(json.dumps({"accepted": len(resolutions), "unresolved": 0}, indent=2))
    print(f"Six-place audit: {RESULT}")
    print(f"Updated 50-place geometries: {V2_GEOMETRIES}")


if __name__ == "__main__":
    main()

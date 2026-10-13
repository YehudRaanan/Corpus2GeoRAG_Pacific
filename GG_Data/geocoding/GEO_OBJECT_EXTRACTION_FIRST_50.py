"""Geocode the first 50 location nodes in the WWII draft graph."""

from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import ijson
from shapely.geometry import shape

from GEO_OBJECT_EXTRACTION_POC import (
    PROJECT_END,
    PROJECT_START,
    USER_AGENT,
    osm_key,
    reconcile_whg,
    source_candidate,
    whg_candidate,
)

ROOT = Path(__file__).parents[2]
GRAPH = (
    ROOT
    / "GG_Data"
    / "agent_export"
    / "outputs"
    / "wwii_agent_graph_draft_v0.1.0.json"
)
CACHE = Path(__file__).with_name("cache")
AUDIT = Path(__file__).with_name("GEO_OBJECT_EXTRACTION_FIRST_50_AUDIT.json")
SUMMARY = Path(__file__).with_name("GEO_OBJECT_EXTRACTION_FIRST_50_SUMMARY.csv")
GEOMETRIES = Path(__file__).with_name("GEO_OBJECT_EXTRACTION_FIRST_50.parquet")
POLICY_VERSION = "geo-object-selection-v0.4.0"

OVERPASS = {
    "OpenHistoricalMap": "https://overpass-api.openhistoricalmap.org/api/interpreter",
    "OpenStreetMap": "https://overpass-api.de/api/interpreter",
}
NOMINATIM = {
    "OpenHistoricalMap": "https://nominatim.openhistoricalmap.org",
    "OpenStreetMap": "https://nominatim.openstreetmap.org",
}

SHIP_TYPES = {"Q12859788", "Q15888", "Q2055880", "Q697196"}


def request_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
) -> Any:
    encoded = urllib.parse.urlencode(params or {})
    if encoded:
        url += "?" + encoded
    body = urllib.parse.urlencode(data).encode() if data else None
    request = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=240) as response:
        return json.load(response)


def first_50_places() -> list[dict[str, Any]]:
    places = []
    with GRAPH.open("rb") as stream:
        for node in ijson.items(stream, "nodes.item"):
            if node.get("type") == "location":
                places.append(node)
            if len(places) == 50:
                return places
    raise RuntimeError("The graph has fewer than 50 location nodes")


def normalized_date(value: Any) -> str | None:
    if not value:
        return None
    match = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", str(value))
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{month or '01'}-{day or '01'}"


def related_dates(qids: set[str]) -> dict[str, list[str]]:
    dates: dict[str, set[str]] = defaultdict(set)
    with GRAPH.open("rb") as stream:
        for edge in ijson.items(stream, "edges.item"):
            linked = qids & {edge.get("source"), edge.get("target")}
            if not linked:
                continue
            raw_dates = [edge.get("start_date"), edge.get("end_date")]
            point_date = (edge.get("attributes") or {}).get("point_date")
            raw_dates.extend(point_date if isinstance(point_date, list) else [point_date])
            in_scope = {
                date
                for value in raw_dates
                if (date := normalized_date(value))
                and PROJECT_START <= date <= PROJECT_END
            }
            for qid in linked:
                dates[qid].update(in_scope)
    return {qid: sorted(dates[qid]) for qid in qids}


def infer_place_type(node: dict[str, Any]) -> str:
    name = node.get("name", "").casefold()
    text = node.get("text", "").casefold()
    p31 = set(node.get("attributes", {}).get("p31", []))
    combined = f"{name} {text}"
    if p31 & SHIP_TYPES or any(term in combined for term in ("ocean liner", "passenger ship")):
        return "not_place"
    if "military government" in combined:
        return "not_place"
    if any(term in combined for term in ("airport", "airfield", "aerodrome")):
        return "airport"
    if "atoll" in combined:
        return "atoll"
    if any(term in combined for term in ("archipelago", "islands")):
        return "archipelago"
    if " island" in combined:
        return "island"
    if any(term in combined for term in ("harbor", "harbour")):
        return "harbor"
    if "mountain range" in combined:
        return "mountain_range"
    if any(term in combined for term in ("concentration camp", "code-breaking site")):
        return "facility"
    if "empire" in name or "former country" in text:
        return "historical_country"
    if "country" in text or "sovereign state" in text or "Q6256" in p31:
        return "country"
    if any(term in text for term in ("city", "town", "village", "settlement")):
        return "settlement"
    if any(
        term in text
        for term in ("municipality", "region", "province", "territory", "area")
    ):
        return "administrative_area"
    return "place"


def prepare_places(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qids = {node["id"] for node in nodes}
    dates_by_qid = related_dates(qids)
    places = []
    for rank, node in enumerate(nodes, 1):
        dates = dates_by_qid[node["id"]]
        places.append(
            {
                "input_rank": rank,
                "qid": node["id"],
                "name": node["name"],
                "description": node.get("text", ""),
                "p31": node.get("attributes", {}).get("p31", []),
                "place_type": infer_place_type(node),
                "related_dates": dates,
                "selection_date": dates[0] if dates else PROJECT_START,
            }
        )
    return places


def cached_overpass(source: str, qids: list[str]) -> list[dict[str, Any]]:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"first_50_{source.casefold()}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("qids") == qids:
            return payload["elements"]
    qid_pattern = "|".join(qids)
    query = (
        f'[out:json][timeout:180];nwr["wikidata"~"^({qid_pattern})$"];'
        "out tags center;"
    )
    response = request_json(OVERPASS[source], data={"data": query})
    elements = response.get("elements", [])
    payload = {
        "qids": qids,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "elements": elements,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload["elements"]


def group_by_qid(
    candidates: list[dict[str, Any]], qids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    grouped = {qid: [] for qid in qids}
    for candidate in candidates:
        qid = candidate.get("tags", {}).get("wikidata")
        if qid in grouped:
            grouped[qid].append(candidate)
    return grouped


def source_date(value: str | None, *, end: bool = False) -> str | None:
    if not value:
        return None
    match = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", value)
    if not match:
        return None
    year, month, day = match.groups()
    if end and not month:
        return f"{int(year) + 1:04d}-01-01"
    if end and not day:
        next_month = int(month) + 1
        if next_month == 13:
            return f"{int(year) + 1:04d}-01-01"
        return f"{year}-{next_month:02d}-01"
    return f"{year}-{month or '01'}-{day or '01'}"


def covers_date(candidate: dict[str, Any], selected_date: str) -> bool:
    tags = candidate.get("tags", {})
    start = source_date(tags.get("start_date"))
    end = source_date(tags.get("end_date"), end=True)
    if not start and not end:
        return True
    return (not start or start <= selected_date) and (not end or selected_date < end)


def type_score(place_type: str, candidate: dict[str, Any]) -> int:
    tags = candidate.get("tags", {})
    values = {str(value).casefold() for value in tags.values()}
    checks = {
        "airport": tags.get("aeroway") in {"aerodrome", "airfield"},
        "atoll": tags.get("natural") == "reef" or tags.get("place") == "atoll",
        "archipelago": tags.get("place") in {"archipelago", "islands"},
        "island": tags.get("place") == "island" or tags.get("natural") == "coastline",
        "harbor": tags.get("water") == "harbour" or "harbour" in values,
        "mountain_range": tags.get("natural") in {"ridge", "mountain_range"},
        "facility": bool(
            set(tags) & {"building", "historic", "landuse", "military", "tourism"}
        ),
        "historical_country": tags.get("boundary") == "administrative",
        "country": tags.get("boundary") == "administrative",
        "settlement": tags.get("boundary") == "administrative"
        or tags.get("place") in {"city", "town", "village", "hamlet"},
        "administrative_area": tags.get("boundary") == "administrative",
        "place": True,
    }
    return 2 if checks.get(place_type, False) else 1


def temporal_key(candidate: dict[str, Any]) -> tuple[str, int, str]:
    start = source_date(candidate.get("tags", {}).get("start_date"))
    first_in_scope = max(start or PROJECT_START, PROJECT_START)
    return first_in_scope, int(start is None), osm_key(candidate)


def select_candidate(
    place: dict[str, Any], candidates: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, str]:
    if place["place_type"] == "not_place":
        return None, "input node is not a place"
    usable = [
        candidate
        for candidate in candidates
        if covers_date(candidate, place["selection_date"])
    ]
    if not usable:
        return None, "no exact-QID candidate covers the selection date"
    best_score = max(type_score(place["place_type"], item) for item in usable)
    best = [item for item in usable if type_score(place["place_type"], item) == best_score]
    selected = min(best, key=temporal_key)
    return selected, (
        f"selected the first of {len(best)} best type-compatible candidate(s) "
        "in the project period"
    )


def cached_whg(places: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / "first_50_whg.json"
    signature = {
        place["qid"]: place["selection_date"] for place in places
    }
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("signature") == signature:
            return payload["results"]
    results = reconcile_whg(places)
    path.write_text(
        json.dumps(
            {
                "signature": signature,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "results": results,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return results


def cached_geometries(
    source: str, candidates: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    if not candidates:
        return {}
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"first_50_{source.casefold()}_geometries.json"
    cached: dict[str, dict[str, Any]] = {}
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
    missing = [item for item in candidates if osm_key(item) not in cached]
    for offset in range(0, len(missing), 50):
        batch = missing[offset : offset + 50]
        rows = request_json(
            NOMINATIM[source] + "/lookup",
            params={
                "osm_ids": ",".join(osm_key(item) for item in batch),
                "format": "jsonv2",
                "polygon_geojson": "1",
                "extratags": "1",
            },
        )
        for row in rows:
            prefix = {"node": "N", "way": "W", "relation": "R"}[row["osm_type"]]
            cached[prefix + str(row["osm_id"])] = row
    path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
    return cached


def geometry_from_row(row: dict[str, Any] | None) -> Any | None:
    if not row or not row.get("geojson"):
        return None
    geometry = shape(row["geojson"])
    return geometry if not geometry.is_empty and geometry.is_valid else None


def main() -> None:
    places = prepare_places(first_50_places())
    qids = [place["qid"] for place in places]
    by_source = {
        source: group_by_qid(cached_overpass(source, qids), qids)
        for source in OVERPASS
    }
    exact_counts = {
        qid: sum(len(by_source[source][qid]) for source in OVERPASS) for qid in qids
    }

    source_selections: dict[
        str, dict[str, tuple[dict[str, Any] | None, str]]
    ] = {}
    for place in places:
        qid = place["qid"]
        source_selections[qid] = {
            source: select_candidate(place, by_source[source][qid])
            for source in OVERPASS
        }

    whg_places = [
        place
        for place in places
        if place["place_type"] != "not_place" and exact_counts[place["qid"]] != 1
    ]
    whg_results = cached_whg(whg_places)

    geometry_rows = {
        source: cached_geometries(
            source,
            [
                selected
                for selections in source_selections.values()
                if (selected := selections[source][0]) is not None
            ],
        )
        for source in OVERPASS
    }

    generated_at = datetime.now(timezone.utc).isoformat()
    audit_rows = []
    geometry_records = []
    geometries = []
    for place in places:
        qid = place["qid"]
        source = None
        selected = None
        geometry = None
        reason = "no exact-QID candidate covers the selection date"
        unavailable_sources = []
        for candidate_source in OVERPASS:
            choice, choice_reason = source_selections[qid][candidate_source]
            if choice is None:
                continue
            candidate_geometry = geometry_from_row(
                geometry_rows[candidate_source].get(osm_key(choice))
            )
            if candidate_geometry is None:
                unavailable_sources.append(candidate_source)
                reason = choice_reason
                continue
            source = candidate_source
            selected = choice
            geometry = candidate_geometry
            reason = choice_reason
            if unavailable_sources:
                reason += "; earlier source had no retrievable valid geometry"
            break
        if place["place_type"] == "not_place":
            status = "REJECTED_NOT_PLACE"
        elif unavailable_sources and geometry is None:
            status = "UNRESOLVED_GEOMETRY"
        elif selected:
            status = "ACCEPTED_AUTO"
        else:
            status = "UNRESOLVED"

        whg_items = whg_results.get(qid, [])
        audit_row = {
            **place,
            "exact_qid_count": exact_counts[qid],
            "source_attempts": [
                {
                    "source": candidate_source,
                    "exact_qid_candidates": len(by_source[candidate_source][qid]),
                    "candidates": [
                        source_candidate(item) for item in by_source[candidate_source][qid]
                    ],
                }
                for candidate_source in OVERPASS
            ],
            "whg": {
                "queried": place in whg_places,
                "candidate_count": len(whg_items),
                "candidates": [whg_candidate(item) for item in whg_items],
            },
            "selected_source": source,
            "selected_object_id": osm_key(selected) if selected else None,
            "review_status": status,
            "decision_reason": reason,
            "geometry_valid": geometry is not None,
        }
        audit_rows.append(audit_row)

        if geometry is not None:
            source_url = (
                f"https://www.openhistoricalmap.org/{selected['type']}/{selected['id']}"
                if source == "OpenHistoricalMap"
                else f"https://www.openstreetmap.org/{selected['type']}/{selected['id']}"
            )
            geometry_records.append(
                {
                    "place_id": qid,
                    "name": place["name"],
                    "place_type": place["place_type"],
                    "selection_date": place["selection_date"],
                    "source_dataset": source,
                    "source_object_id": osm_key(selected),
                    "source_url": source_url,
                    "match_method": "EXACT_WIKIDATA_QID",
                    "selection_policy_version": POLICY_VERSION,
                    "retrieved_at": generated_at,
                    "review_status": status,
                    "decision_reason": reason,
                }
            )
            geometries.append(geometry)

    status_counts = defaultdict(int)
    for row in audit_rows:
        status_counts[row["review_status"]] += 1
    output = {
        "policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "input": {
            "graph": str(GRAPH.relative_to(ROOT)),
            "selection": "first 50 nodes classified as location, in graph order",
            "project_date_range": {"start": PROJECT_START, "end": PROJECT_END},
        },
        "summary": {
            "input_nodes": len(places),
            "status_counts": dict(status_counts),
            "geometry_rows": len(geometry_records),
            "whg_queries": len(whg_places),
            "whg_api_requests": 1 if whg_places else 0,
        },
        "results": audit_rows,
    }
    AUDIT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

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
    with SUMMARY.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(audit_rows)

    frame = gpd.GeoDataFrame(geometry_records, geometry=geometries, crs=None)
    frame.to_parquet(GEOMETRIES, index=False)
    print(json.dumps(output["summary"], indent=2))
    print(f"Audit: {AUDIT}")
    print(f"Summary: {SUMMARY}")
    print(f"Shapely geometries: {GEOMETRIES}")


if __name__ == "__main__":
    main()

"""Run the small geo-object source-order proof of concept."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import shape

PROJECT_START = "1941-12-07"
PROJECT_END = "1945-09-02"
USER_AGENT = (
    "Corpus2GeoRAG-Pacific-geocoding-POC/0.2 "
    "(+https://github.com/EtzionR/Corpus2GeoRAG_Pacific)"
)
OUTPUT = Path(__file__).with_name("GEO_OBJECT_EXTRACTION_POC_RESULT.json")
ENV_FILE = Path(__file__).parents[2] / ".env"

PLACES = [
    {"qid": "Q34664", "name": "Hiroshima", "place_type": "city"},
    {"qid": "Q127091", "name": "Pearl Harbor", "place_type": "harbor"},
    {"qid": "Q43296", "name": "Wake Island", "place_type": "atoll"},
    {
        "qid": "Q12259031",
        "name": "Henderson Field",
        "place_type": "former_airfield",
    },
    {
        "qid": "Q15180",
        "name": "Soviet Union",
        "place_type": "historical_country",
    },
]


def get_json(url: str, params: dict[str, str]) -> Any:
    request = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def env_value(name: str) -> str:
    """Read one local setting without adding a dotenv dependency."""
    for raw_line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if value:
            return value
    raise RuntimeError(f"{name} is missing from {ENV_FILE}")


def place_selection_date(place: dict[str, Any]) -> str:
    """Use the earliest related date in scope, or the start of the project scope."""
    dates = sorted(
        date
        for date in place.get("related_dates", [])
        if PROJECT_START <= date <= PROJECT_END
    )
    return dates[0] if dates else PROJECT_START


def reconcile_whg(places: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Reconcile all exceptional cases in one quota-efficient WHG request."""
    if not places:
        return {}
    if len(places) > 50:
        raise ValueError("The WHG POC batch cannot exceed 50 queries")
    queries = {}
    for place in places:
        year = int(place_selection_date(place)[:4])
        queries[place["qid"]] = {
            "query": place["name"],
            "start": year,
            "end": year,
            "undated": True,
            "temporal_mode": "definitely",
            "limit": 10,
        }
    request = urllib.request.Request(
        "https://whgazetteer.org/reconcile",
        data=json.dumps({"queries": queries}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {env_value('WHG_key')}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    return {
        place["qid"]: payload.get(place["qid"], {}).get("result", [])
        for place in places
    }


def exact_qid_candidates(endpoint: str, qids: list[str]) -> list[dict[str, Any]]:
    candidates = []
    for qid in qids:
        query = f'[out:json][timeout:45];nwr["wikidata"="{qid}"];' "out tags center;"
        candidates.extend(get_json(endpoint, {"data": query})["elements"])
    return candidates


def osm_name_candidates(place: dict[str, str]) -> list[dict[str, Any]]:
    """Find OSM candidates by name and retain their source tags."""
    query = (
        f"{place['name']}, Guadalcanal"
        if place["qid"] == "Q12259031"
        else place["name"]
    )
    rows = get_json(
        "https://nominatim.openstreetmap.org/search",
        {
            "q": query,
            "format": "jsonv2",
            "extratags": "1",
            "limit": "50",
        },
    )
    candidates = []
    for row in rows:
        tags = dict(row.get("extratags") or {})
        if row.get("category") and row.get("type"):
            tags[row["category"]] = row["type"]
        tags["name"] = row.get("name")
        candidates.append(
            {
                "type": row["osm_type"],
                "id": row["osm_id"],
                "tags": tags,
                "display_name": row.get("display_name"),
            }
        )
    return candidates


def contains_date(tags: dict[str, str], selected_date: str) -> bool:
    start = tags.get("start_date", "")
    end = tags.get("end_date", "")
    if not start and not end:
        return True
    return (not start or start <= selected_date) and (not end or end > selected_date)


def temporal_order(item: dict[str, Any]) -> tuple[str, int, str]:
    """Put the first applicable dated object first; use source ID as a stable tie-break."""
    tags = item.get("tags", {})
    start = tags.get("start_date") or PROJECT_START
    first_date_in_scope = max(start, PROJECT_START)
    return first_date_in_scope, int(not tags.get("start_date")), osm_key(item)


def type_score(place_type: str, tags: dict[str, str]) -> int:
    rules = {
        "city": tags.get("boundary") == "administrative",
        "harbor": tags.get("water") == "harbour",
        "atoll": tags.get("natural") == "reef",
        "former_airfield": tags.get("aeroway") in {"aerodrome", "airfield"},
        "historical_country": tags.get("boundary") == "administrative",
    }
    return 1 if rules[place_type] else 0


def select_one(
    place: dict[str, str], candidates: list[dict[str, Any]], historical: bool
) -> tuple[dict[str, Any] | None, str]:
    selected_date = place_selection_date(place)
    usable = candidates
    if historical:
        usable = [
            item
            for item in usable
            if contains_date(item.get("tags", {}), selected_date)
        ]
    scored = [
        item
        for item in usable
        if type_score(place["place_type"], item.get("tags", {})) == 1
    ]
    if len(scored) == 1:
        return scored[0], "one exact-QID candidate passed the date and type rules"
    if not scored:
        return None, "no exact-QID candidate passed the date and type rules"
    selected = min(scored, key=temporal_order)
    return selected, f"selected the first of {len(scored)} candidates in the project period"


def osm_key(item: dict[str, Any]) -> str:
    return {"node": "N", "way": "W", "relation": "R"}[item["type"]] + str(item["id"])


def geometry_summary(nominatim: str, item: dict[str, Any]) -> dict[str, Any]:
    rows = get_json(
        nominatim + "/lookup",
        {
            "osm_ids": osm_key(item),
            "format": "jsonv2",
            "polygon_geojson": "1",
            "extratags": "1",
        },
    )
    if len(rows) != 1 or not rows[0].get("geojson"):
        raise ValueError(f"Full geometry lookup failed for {osm_key(item)}")
    geometry = shape(rows[0]["geojson"])
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"Invalid geometry for {osm_key(item)}")

    def vertices(value: Any) -> int:
        if hasattr(value, "geoms"):
            return sum(vertices(part) for part in value.geoms)
        if value.geom_type == "Polygon":
            return len(value.exterior.coords) + sum(
                len(ring.coords) for ring in value.interiors
            )
        return len(value.coords) if hasattr(value, "coords") else 0

    return {
        "shapely_type": geometry.geom_type,
        "is_valid": geometry.is_valid,
        "is_empty": geometry.is_empty,
        "vertex_count": vertices(geometry),
        "bounds": [round(number, 6) for number in geometry.bounds],
    }


def source_candidate(item: dict[str, Any]) -> dict[str, Any]:
    tags = item.get("tags", {})
    return {
        "object_type": item["type"],
        "object_id": item["id"],
        "name": tags.get("name"),
        "start_date": tags.get("start_date"),
        "end_date": tags.get("end_date"),
        "boundary": tags.get("boundary"),
        "natural": tags.get("natural"),
        "water": tags.get("water"),
        "place": tags.get("place"),
        "aeroway": tags.get("aeroway"),
    }


def whg_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "score": item.get("score"),
        "confidence": item.get("confidence"),
        "match": item.get("match"),
        "has_geom": item.get("has_geom"),
    }


def whg_source_id(source: str, item: dict[str, Any]) -> str:
    namespace = "ohm" if source == "OpenHistoricalMap" else "osm"
    return f"place:{namespace}:{osm_key(item).lower()}"


def main() -> None:
    qids = [place["qid"] for place in PLACES]
    ohm = exact_qid_candidates(
        "https://overpass-api.openhistoricalmap.org/api/interpreter", qids
    )
    ohm_by_qid = {qid: [] for qid in qids}
    for item in ohm:
        ohm_by_qid[item.get("tags", {}).get("wikidata")].append(item)

    osm_names_by_qid = {place["qid"]: osm_name_candidates(place) for place in PLACES}
    osm_by_qid = {
        place["qid"]: [
            item
            for item in osm_names_by_qid[place["qid"]]
            if item.get("tags", {}).get("wikidata") == place["qid"]
        ]
        for place in PLACES
    }
    exact_counts = {qid: len(ohm_by_qid[qid]) + len(osm_by_qid[qid]) for qid in qids}
    selections = {}
    for place in PLACES:
        qid = place["qid"]
        ohm_selection = select_one(place, ohm_by_qid[qid], historical=True)
        osm_selection = select_one(place, osm_by_qid[qid], historical=True)
        selections[qid] = (ohm_selection, osm_selection)
    whg_required = [place for place in PLACES if exact_counts[place["qid"]] != 1]
    whg_required_qids = {place["qid"] for place in whg_required}
    whg_results = reconcile_whg(whg_required)

    results = []
    for place in PLACES:
        qid = place["qid"]
        row: dict[str, Any] = {
            **place,
            "selection_date": place_selection_date(place),
            "source_attempts": [],
            "selected_source": None,
            "selected_object_id": None,
            "geometry": None,
            "review_status": "UNRESOLVED",
            "release_ready": False,
        }

        (ohm_selected, ohm_reason), (osm_selected, osm_reason) = selections[qid]
        row["source_attempts"].append(
            {
                "source": "OpenHistoricalMap",
                "exact_qid_candidates": len(ohm_by_qid[qid]),
                "candidates": [source_candidate(item) for item in ohm_by_qid[qid]],
                "decision": ohm_reason,
            }
        )
        row["source_attempts"].append(
            {
                "source": "OpenStreetMap",
                "access_method": (
                    "Nominatim name discovery followed by exact-QID filtering; "
                    "public Overpass endpoints timed out"
                ),
                "name_candidates": len(osm_names_by_qid[qid]),
                "exact_qid_candidates": len(osm_by_qid[qid]),
                "candidates": [source_candidate(item) for item in osm_by_qid[qid]],
                "decision": osm_reason,
            }
        )

        selected = ohm_selected or osm_selected
        selected_source = "OpenHistoricalMap" if ohm_selected else "OpenStreetMap"
        selection_reason = ohm_reason if ohm_selected else osm_reason

        needs_whg = qid in whg_required_qids
        whg_items = whg_results.get(qid, [])
        selected_whg_id = whg_source_id(selected_source, selected) if selected else None
        whg_supports_selection = (
            selected_whg_id in {item.get("id") for item in whg_items}
            if selected_whg_id
            else None
        )
        if needs_whg:
            if exact_counts[qid] == 0:
                trigger = "no exact-QID object was found"
            elif exact_counts[qid] > 1:
                trigger = f"{exact_counts[qid]} exact-QID objects were found"
            else:
                trigger = "the exact-QID objects need reconciliation"
            row["source_attempts"].append(
                {
                    "source": "World Historical Gazetteer",
                    "status": "QUERIED_IN_SHARED_BATCH",
                    "trigger": trigger,
                    "candidate_count": len(whg_items),
                    "candidates": [whg_candidate(item) for item in whg_items],
                    "selected_source_object_in_results": whg_supports_selection,
                    "decision": (
                        "WHG supplies candidates; the project period and type rules "
                        "make the final selection."
                    ),
                }
            )
        else:
            row["source_attempts"].append(
                {
                    "source": "World Historical Gazetteer",
                    "status": "SKIPPED",
                    "decision": "Exactly one exact-QID object was found.",
                }
            )

        if selected:
            if selected_source == "OpenHistoricalMap":
                source_url = (
                    "https://www.openhistoricalmap.org/"
                    f"{selected['type']}/{selected['id']}"
                )
                nominatim = "https://nominatim.openhistoricalmap.org"
            else:
                source_url = (
                    f"https://www.openstreetmap.org/{selected['type']}/{selected['id']}"
                )
                nominatim = "https://nominatim.openstreetmap.org"
            row.update(
                selected_source=selected_source,
                selected_object_id=osm_key(selected),
                source_url=source_url,
                geometry=geometry_summary(nominatim, selected),
                review_status="ACCEPTED_AUTO",
                release_ready=True,
                decision_reason=selection_reason,
            )
            results.append(row)
            continue

        row["source_attempts"].append(
            {
                "source": "Nominatim name search",
                "candidate_count": len(osm_names_by_qid[qid]),
                "candidates": [
                    {
                        "object_type": item.get("type"),
                        "object_id": item.get("id"),
                        "display_name": item.get("display_name"),
                        "wikidata": item.get("tags", {}).get("wikidata"),
                    }
                    for item in osm_names_by_qid[qid]
                ],
                "decision": "name-only candidates are not accepted automatically",
            }
        )
        row["decision_reason"] = (
            "No exact-QID geometry passed the source, project-period, and type rules."
        )
        results.append(row)

    output = {
        "policy_version": "geo-object-selection-v0.4.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_date_range": {"start": PROJECT_START, "end": PROJECT_END},
        "selection_flow": [
            "collect exact-QID objects from OpenHistoricalMap and OpenStreetMap",
            "use the earliest related date in the project period, or the project start when no related date exists",
            "allow an undated source object; reject a dated object that does not cover the selection date",
            "query World Historical Gazetteer only when the exact-QID count is zero or greater than one",
            "apply the place-type rule",
            "when several candidates remain, select the first in the project period",
            "use name and alias candidates only as unresolved evidence",
        ],
        "summary": {
            "places": len(results),
            "accepted_auto": sum(
                row["review_status"] == "ACCEPTED_AUTO" for row in results
            ),
            "release_ready": sum(row["release_ready"] for row in results),
            "whg_requests": 1 if whg_required else 0,
            "whg_queries": len(whg_required),
            "whg_skipped": len(results) - len(whg_required),
            "unresolved": sum(row["review_status"] == "UNRESOLVED" for row in results),
        },
        "results": results,
    }
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(output["summary"], indent=2))
    for row in results:
        print(
            row["qid"],
            row["name"],
            row["review_status"],
            row["selected_source"],
            row["selected_object_id"],
            row["release_ready"],
        )


if __name__ == "__main__":
    main()

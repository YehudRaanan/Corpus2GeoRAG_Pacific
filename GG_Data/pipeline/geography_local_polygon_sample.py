"""Cached ten-input test of the owner-approved broader-polygon fallback.

Population S2T 9.2 / GEOCODING_HIGH_LEVEL_PROCESS.md apply. This is a
sample-only selection rule: smallest supported existing local polygon covering
all plausible saved locations. No new identity, name threshold or source is
introduced. Candidate coverage is limited to the pinned saved searches.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd
from pyproj import Geod
from shapely.geometry import Point, shape

from .geography_context_sample import exact_alias
from .graph_contract import load_geometry
from .poc import digest, read_json
from .rebuild_poc import write


def smallest_covering_polygon(candidates: list[dict], locations: list) -> dict | None:
    """Require verified local scope and full containment; never build a shape.

    Country/larger/unknown scope cannot pass. Minimum is among the retrieved
    supported polygons only, not every polygon that exists in the world.
    """
    if not locations:
        return None
    eligible = []
    geod = Geod(ellps="WGS84")
    for candidate in candidates:
        geometry = candidate["geometry"]
        if (
            candidate["scope"] != "local"
            or geometry.geom_type not in {"Polygon", "MultiPolygon"}
            or geometry.is_empty
            or not geometry.is_valid
            or not all(geometry.covers(g) for g in locations)
        ):
            continue
        area = abs(geod.geometry_area_perimeter(geometry)[0]) / 1_000_000
        if area <= 0:
            raise ValueError("Nonpositive geodesic polygon area")
        eligible.append(candidate | {"area_km2": area})
    return (
        min(eligible, key=lambda c: (c["area_km2"], c["source_id"]))
        if eligible
        else None
    )


def source_local_scope(row: dict) -> bool:
    """Recognize explicit local administrative metadata in this cached test.

    Missing metadata fails closed. This is not a new global hierarchy mapping:
    non-administrative polygons and unknown scope need further evidence.
    """
    tags, address = row.get("extratags") or {}, row.get("address") or {}
    level = tags.get("admin_level", "")
    return (
        row.get("type") == "administrative"
        and str(level).isdigit()
        and int(level) > 2
        and row.get("addresstype") not in {"country", "continent"}
        and any(
            row.get("name") == address.get(key)
            for key in ("city", "town", "village", "municipality", "borough", "county")
        )
    )


def date_eligible(row: dict, date: str) -> bool:
    """Reuse supplied-prefix date comparison; preserve undated eligibility."""
    tags = row.get("extratags") or {}
    for key in ("start_date", "end_date"):
        value = tags.get(key)
        if value and not re.fullmatch(r"\d{4}(?:-\d{2}){0,2}", value):
            raise ValueError(f"Unsupported source date: {value}")
    return not (
        tags.get("start_date", "")[: len(date)] > date
        or (tags.get("end_date") and tags["end_date"][: len(date)] < date)
    )


def run(base: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Preserve prior outputs; choose a new directory")
    prior = base / "geography_context_parent_checked"
    audit = read_json(prior / "audit.json")
    sample = read_json(base / "geography_sample/sample.json")
    analysis = read_json(base / "geography_candidate_analysis/candidate_review.json")
    protected = dict(audit["protected_sha256"]) | dict(audit["source_sha256"])
    for folder in (prior, base / "geography_sample", base / "model_qid_name"):
        protected.update({str(p): digest(p) for p in folder.iterdir() if p.is_file()})
    analysis_path = base / "geography_candidate_analysis/candidate_review.json"
    protected[str(analysis_path)] = digest(analysis_path)
    for filename, expected in protected.items():
        if digest(Path(filename)) != expected:
            raise ValueError(f"Changed pinned source: {filename}")
    if len(sample) != 10 or [p["place_id"] for p in sample] != [
        r["input"]["place_id"] for r in audit["results"]
    ]:
        raise ValueError("Expected the same ten inputs in the same order")
    reviews = {r["place_id"]: r for r in analysis["reviews"]}
    results, geometries = [], []
    for old in audit["results"]:
        place, clue = old["input"], old["context"]
        pid, name = place["place_id"], place["name"]
        row = dict(
            input=place, result="UNRESOLVED", approximate=None, geometry_ref=None
        )
        geometry = None
        if old["review_status"] == "ACCEPTED_AUTO":
            geometry = load_geometry(old["geometry_ref"], prior)
            row.update(
                result="RETAINED_ACCEPTED",
                approximate=False,
                source_dataset=old["source_dataset"],
                source_object_id=old["source_object_id"],
                decision_reason="Existing verified exact-QID geometry retained unchanged",
            )
        else:
            # Parent evidence was independently checked in the prior approved
            # run. Do not turn a candidate's address or page title into proof.
            supporting = {
                (c["source"], c["source_id"])
                for p in clue["parents"]
                for c in p["supporting_candidates"]
            }
            locations, polygons = [], []
            for candidate in reviews[pid].get("candidates", []):
                if (
                    candidate["source"] == "GeoNames"
                    and (candidate["source"], candidate["source_id"]) in supporting
                    and exact_alias(name, candidate.get("aliases", []))
                ):
                    locations.append(Point(*candidate["coordinate"]))
            for path in sorted((prior / "sources").glob(f"{pid}_*.json")):
                saved = read_json(path)
                for candidate in saved["rows"]:
                    source_id = f"{candidate['osm_type']}:{candidate['osm_id']}"
                    endpoint = (
                        "https://nominatim.openstreetmap.org/search"
                        if path.stem.endswith("OpenStreetMap")
                        else "https://nominatim.openhistoricalmap.org/search"
                    )
                    aliases = [candidate.get("name", "")]
                    for value in (candidate.get("namedetails") or {}).values():
                        if isinstance(value, str):
                            aliases.extend(value.split(";"))
                    if (
                        (endpoint, source_id) not in supporting
                        or not exact_alias(name, aliases)
                        or not date_eligible(candidate, place["selection_date"])
                    ):
                        continue
                    native = candidate.get("geojson")
                    if not native:
                        continue
                    geo = shape(native)
                    if geo.is_empty or not geo.is_valid:
                        raise ValueError(f"Invalid saved source geometry: {source_id}")
                    locations.append(geo)
                    polygons.append(
                        dict(
                            source_id=source_id,
                            source_dataset=endpoint,
                            geometry=geo,
                            scope="local"
                            if source_local_scope(candidate)
                            else "unknown",
                            source_file=str(path),
                            source_name=candidate.get("name"),
                        )
                    )
            choice = smallest_covering_polygon(polygons, locations)
            row.update(
                supported_location_count=len(locations),
                saved_polygon_count=sum(
                    p["geometry"].geom_type in {"Polygon", "MultiPolygon"}
                    for p in polygons
                ),
                verified_parents=clue["parents"],
            )
            if choice:
                geometry = choice["geometry"]
                row.update(
                    result="APPROXIMATE_LOCAL_POLYGON",
                    approximate=True,
                    source_dataset=choice["source_dataset"],
                    source_object_id=choice["source_id"],
                    source_name=choice["source_name"],
                    area_km2=choice["area_km2"],
                    decision_reason="Smallest supported retrieved local polygon covers every plausible saved location; exact feature identity remains uncertain",
                )
            else:
                row["decision_reason"] = (
                    "Punctuation-only input: no geographic name"
                    if not any(c.isalnum() for c in name)
                    else "No independently verified parent clue; broader-area assignment is not supported"
                    if not clue["parents"]
                    else "No supported original local polygon covering the plausible locations in saved searches"
                )
        if geometry is not None:
            geometries.append(dict(place_id=pid, geometry=geometry))
        results.append(row)
    output.mkdir(parents=True)
    artifact = output / "geometries.parquet"
    gpd.GeoDataFrame(geometries, geometry="geometry", crs="EPSG:4326").to_parquet(
        artifact, index=False
    )
    for row in results:
        if row["result"] == "UNRESOLVED":
            continue
        pointer = dict(
            file=artifact.name,
            place_id=row["input"]["place_id"],
            sha256=digest(artifact),
        )
        expected = next(
            g["geometry"] for g in geometries if g["place_id"] == pointer["place_id"]
        )
        if not load_geometry(pointer, output).equals_exact(expected, 0):
            raise ValueError("Shapely round trip changed geometry")
        row["geometry_ref"] = pointer
    if any(digest(Path(p)) != expected for p, expected in protected.items()):
        raise ValueError("Protected source or model changed")
    report = dict(
        status="VERIFIED_CACHED_TEN_LOCAL_POLYGON_TEST",
        results=results,
        retained_accepted=sum(r["result"] == "RETAINED_ACCEPTED" for r in results),
        approximate=sum(r["result"] == "APPROXIMATE_LOCAL_POLYGON" for r in results),
        unresolved=sum(r["result"] == "UNRESOLVED" for r in results),
        inputs=10,
        new_requests=0,
        main_model_changed=False,
        identity_assignments_changed=False,
        pointers_in_model_only=True,
        scope="Cached evidence only; minimum among supported retrieved polygons, not global minimum",
        protected_sha256=protected,
    )
    write(output / "audit.json", report)
    write(
        output / "verification.json",
        {k: v for k, v in report.items() if k not in {"results", "protected_sha256"}}
        | dict(
            geometry_roundtrip_exact=True,
            protected_hashes_unchanged=True,
            outputs={p.name: digest(p) for p in output.iterdir() if p.is_file()},
        ),
    )
    return {
        k: report[k]
        for k in (
            "status",
            "inputs",
            "retained_accepted",
            "approximate",
            "unresolved",
            "new_requests",
        )
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.base.resolve(), args.output.resolve())))

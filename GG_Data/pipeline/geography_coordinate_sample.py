"""Test population S2T 9.3 on the same ten frozen Geography inputs.

Reuse accepted geometry and pinned Wikidata records. Candidate coordinates may
guide retrieval but cannot establish their own identity. No model/ID changes.
Nominatim public policy: single thread, identifying User-Agent, cached requests,
at least one second between calls. Reverse results are candidates, not truth.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
from pyproj import Geod
from shapely.geometry import Point, shape

from .geography_context_sample import exact_alias
from .geography_sample import tools
from .graph_contract import load_geometry
from .poc import digest, read_json
from .rebuild_poc import write


def coordinate(entity: dict) -> dict | None:
    """Preserve the single original Earth coordinate; never rank conflicts.

    S2T 9.3 requires consultation for conflicting/unsupported representations.
    Missing coordinates are expected coverage gaps, not invented positions.
    """
    claims = entity.get("claims", {}).get("P625", [])
    if not claims:
        return None
    if len(claims) != 1:
        raise ValueError(f"Coordinate statements need review: {entity['id']}")
    claim = claims[0]
    snak = claim["mainsnak"]
    if snak.get("snaktype") != "value" or claim.get("rank") == "deprecated":
        raise ValueError(f"Unsupported coordinate statement: {entity['id']}")
    value = snak["datavalue"]["value"]
    lon, lat = value["longitude"], value["latitude"]
    if (
        value.get("globe") != "http://www.wikidata.org/entity/Q2"
        or not all(type(v) in {int, float} and math.isfinite(v) for v in (lon, lat))
        or not (-180 <= lon <= 180 and -90 <= lat <= 90)
        or value.get("altitude") is not None
    ):
        raise ValueError(f"Unsupported coordinate representation: {entity['id']}")
    return dict(qid=entity["id"], statement=claim, xy=[lon, lat], crs="EPSG:4326")


def fallback_point(
    evidence: dict | None, *, identity_supported: bool, has_geometry: bool
):
    """S2T 9.3: never replace supported geometry or bypass identity evidence."""
    if evidence is None or not identity_supported or has_geometry:
        return None
    return Point(*evidence["xy"])


def run(
    base: Path,
    prior: Path,
    candidate_cache: Path,
    output: Path,
    request_cache: Path | None = None,
) -> dict:
    if output.exists():
        raise ValueError("Preserve old results; use a new output directory")
    old = read_json(prior / "audit.json")
    sample = read_json(base / "geography_sample/sample.json")
    if len(sample) != 10 or [p["place_id"] for p in sample] != [
        r["input"]["place_id"] for r in old["results"]
    ]:
        raise ValueError("Expected the same ten inputs in the same order")
    protected = dict(old["protected_sha256"])
    paths = [p for p in prior.iterdir() if p.is_file()]
    paths += [base / "entities/full_records.json.gz", base / "entities/manifest.json"]
    paths += [
        base / "geography_candidate_analysis/candidate_review.json",
        candidate_cache,
    ]
    snapshot_path = candidate_cache.parent / "table_snapshot.json"
    paths.append(snapshot_path)
    protected.update({str(p): digest(p) for p in paths})
    if any(digest(Path(p)) != sha for p, sha in protected.items()):
        raise ValueError("Protected source differs")
    manifest = read_json(base / "entities/manifest.json")
    snapshot = read_json(snapshot_path)
    if snapshot["snapshot_at"] != manifest["snapshot_at"]:
        raise ValueError("Candidate snapshot differs from agreed snapshot")
    cached = read_json(candidate_cache)
    sql_path = candidate_cache.with_suffix("").with_suffix(".sql")
    if digest(sql_path) != cached["sql_sha256"]:
        raise ValueError("Candidate query hash differs")
    protected[str(sql_path)] = digest(sql_path)
    if snapshot["snapshot_at"] not in sql_path.read_text(encoding="utf-8"):
        raise ValueError("Candidate query does not use the pinned snapshot")
    raw = read_json(base / "entities/full_records.json.gz")
    reviews = read_json(base / "geography_candidate_analysis/candidate_review.json")
    reviews = {r["place_id"]: r for r in reviews["reviews"]}
    # Only explicit saved WHG Wikidata links with an existing exact alias enter
    # this retrieval test. Superseded previous_place_id values are never used.
    candidates = {}
    for place in sample:
        candidates[place["place_id"]] = sorted(
            {
                c["source_id"].split(":")[-1]
                for c in reviews[place["place_id"]]["candidates"]
                if c["source"] == "WHG"
                and c["source_id"].startswith("place:wd:")
                and exact_alias(place["name"], c.get("aliases", []))
            }
        )
    wanted = {q for qs in candidates.values() for q in qs}
    records = {}
    for row in cached["rows"]:
        if row["id"] in wanted:
            entity = json.loads(row["item"].rstrip(",\r\n "))
            if entity["id"] != row["id"] or row["id"] in records:
                raise ValueError("Candidate record ID mismatch/duplicate")
            records[row["id"]] = entity
    if wanted - records.keys():
        raise ValueError(
            f"Candidate records unavailable: {sorted(wanted-records.keys())}"
        )
    output.mkdir(parents=True)
    sources = output / "sources"
    sources.mkdir()
    client, geod = tools(), Geod(ellps="WGS84")
    results, geometries, requests, reused = [], [], 0, 0
    report = dict(status="RUNNING", inputs=10, results=results)
    try:
        for previous in old["results"]:
            place = previous["input"]
            pid = place["place_id"]
            row = dict(previous, coordinate_checks=[], geometry_ref=None)
            geometry = (
                load_geometry(previous["geometry_ref"], prior)
                if previous["geometry_ref"]
                else None
            )
            qids = [place["wikidata_id"]] if place["wikidata_id"] else candidates[pid]
            for qid in qids:
                matched = place["wikidata_id"] == qid
                entity = raw[qid]["entity"] if matched else records[qid]
                evidence = coordinate(entity)
                check = dict(
                    qid=qid,
                    role="MATCHED_INPUT" if matched else "CANDIDATE_ONLY",
                    evidence=evidence,
                )
                row["coordinate_checks"].append(check)
                if evidence is None:
                    check["decision"] = "NO_P625"
                    continue
                params = dict(
                    lat=str(evidence["xy"][1]),
                    lon=str(evidence["xy"][0]),
                    format="jsonv2",
                    polygon_geojson="1",
                    namedetails="1",
                    extratags="1",
                    addressdetails="1",
                )
                url = client.NOMINATIM["OpenStreetMap"] + "/reverse"
                filename = f"{pid}_{qid}.json"
                saved_path = request_cache / filename if request_cache else None
                if saved_path and saved_path.exists():
                    saved = read_json(saved_path)
                    if saved["url"] != url or saved["params"] != params:
                        raise ValueError("Cached coordinate request differs")
                    protected[str(saved_path)] = digest(saved_path)
                    reused += 1
                else:
                    response = client.request_json(url, params=params)
                    requests += 1
                    saved = dict(
                        url=url,
                        params=params,
                        response=response,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                    )
                    time.sleep(1.1)
                write(sources / filename, saved)
                response = saved["response"]
                if not isinstance(response, dict) or "error" in response:
                    raise ValueError(f"Incomplete Nominatim reverse result: {qid}")
                returned_qid = (response.get("extratags") or {}).get("wikidata")
                check.update(
                    reverse_object_id=f"{response.get('osm_type')}:{response.get('osm_id')}",
                    reverse_name=response.get("name"),
                    reverse_qid=returned_qid,
                    reverse_qid_agreement=returned_qid == qid,
                    reverse_is_identity_proof=False,
                )
                if response.get("geojson"):
                    candidate_geo = shape(response["geojson"])
                    if not candidate_geo.is_valid or candidate_geo.is_empty:
                        raise ValueError(f"Invalid reverse geometry: {qid}")
                    check.update(
                        reverse_geometry_type=candidate_geo.geom_type,
                        coordinate_covered=candidate_geo.covers(Point(*evidence["xy"])),
                    )
                # Distances are diagnostic only: no new tolerance or nearest
                # acceptance is authorized. Both sources may share GeoNames.
                comparisons = []
                linked_ids = {
                    c["mainsnak"].get("datavalue", {}).get("value")
                    for c in entity.get("claims", {}).get("P1566", [])
                }
                for c in reviews[pid]["candidates"]:
                    if (
                        c["source"] == "GeoNames"
                        and c.get("coordinate")
                        and (
                            c["source_id"] in linked_ids
                            or exact_alias(place["name"], c.get("aliases", []))
                        )
                    ):
                        comparisons.append(
                            dict(
                                source_id=c["source_id"],
                                linked_by_P1566=c["source_id"] in linked_ids,
                                distance_m=geod.inv(*evidence["xy"], *c["coordinate"])[
                                    2
                                ],
                                independent_identity_proof=False,
                            )
                        )
                check["saved_candidate_distances"] = comparisons
                check["decision"] = (
                    "RETAIN_EXISTING_GEOMETRY"
                    if geometry is not None
                    else "CANDIDATE_COORDINATE_CANNOT_PROVE_INPUT_IDENTITY"
                )
                point = fallback_point(
                    evidence,
                    identity_supported=matched,
                    has_geometry=geometry is not None,
                )
                if point is not None:
                    geometry = point
                    row.update(
                        result="WIKIDATA_POINT_FALLBACK",
                        approximate=False,
                        source_dataset="Wikidata",
                        source_object_id=evidence["statement"]["id"],
                        decision_reason="Supported input coordinate; no other accepted geometry",
                    )
            if geometry is not None:
                geometries.append(dict(place_id=pid, geometry=geometry))
            if not row["coordinate_checks"]:
                row["coordinate_reason"] = (
                    "Supported geometry already available; no coordinate fallback needed"
                    if geometry is not None
                    else "No matched input QID or exact-alias saved Wikidata candidate link; do not invent a QID"
                )
            results.append(row)
            write(
                output / "progress.json",
                dict(completed=len(results), new_requests=requests),
            )
    except Exception as error:
        write(
            output / "stop.json",
            dict(
                status="STOPPED_FOR_CONSULTATION",
                error=str(error),
                results=results,
                new_requests=requests,
            ),
        )
        raise
    artifact = output / "geometries.parquet"
    gpd.GeoDataFrame(geometries, geometry="geometry", crs="EPSG:4326").to_parquet(
        artifact, index=False
    )
    for row in results:
        expected = next(
            (
                g["geometry"]
                for g in geometries
                if g["place_id"] == row["input"]["place_id"]
            ),
            None,
        )
        if expected is not None:
            pointer = dict(
                file=artifact.name,
                place_id=row["input"]["place_id"],
                sha256=digest(artifact),
            )
            if not load_geometry(pointer, output).equals_exact(expected, 0):
                raise ValueError("Geometry round trip changed coordinates")
            row["geometry_ref"] = pointer
    if any(digest(Path(p)) != sha for p, sha in protected.items()):
        raise ValueError("Protected evidence/model changed")
    report.update(
        status="VERIFIED_TEN_COORDINATE_TEST",
        new_requests=requests,
        reused_requests=reused,
        accepted=len(geometries),
        unresolved=10 - len(geometries),
        new_fallback_points=sum(
            r["result"] == "WIKIDATA_POINT_FALLBACK" for r in results
        ),
        snapshot_at=manifest["snapshot_at"],
        main_model_changed=False,
        identity_assignments_changed=False,
        protected_sha256=protected,
        geometry_roundtrip_exact=True,
    )
    write(output / "audit.json", report)
    summary = {
        k: v for k, v in report.items() if k not in {"results", "protected_sha256"}
    }
    write(
        output / "verification.json",
        summary
        | dict(
            protected_hashes_unchanged=True,
            outputs={
                str(p.relative_to(output)): digest(p)
                for p in output.rglob("*")
                if p.is_file()
            },
        ),
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("base", "prior", "candidate-cache", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--request-cache", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.base,
                args.prior,
                args.candidate_cache,
                args.output,
                args.request_cache,
            )
        )
    )

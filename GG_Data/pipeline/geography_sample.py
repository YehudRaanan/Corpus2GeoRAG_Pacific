"""Recheck the fixed ten Geography inputs after the page-scope correction.

Population S2T 3/9 and geo-object-selection-v0.5.0 apply. This bounded sample
reuses the existing source clients and selection functions. It is not the
full Geography importer. Prior accepted identities/geometry decisions are
never imported; only original source responses can be reused.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from .graph_contract import load_geometry
from .poc import ROOT, digest, read_json
from .rebuild_poc import write
from .relations import SourceException


def tools():
    """Reuse the established source clients despite their legacy sibling imports."""
    sys.path.insert(0, str(ROOT / "GG_Data/geocoding"))
    try:
        return importlib.import_module("GEO_OBJECT_EXTRACTION_FIRST_50")
    finally:
        sys.path.pop(0)


def run(base: Path, *, model_dir: Path | None = None) -> dict:
    output, cache = base / "geography_sample", base / "geography_sources"
    original = ROOT / "GG_Data/pipeline/outputs/poc_geography_10_sources_20261022"
    if (output / "verification.json").exists():
        raise ValueError("Preserve the completed Geography sample")
    sample = read_json(output / "sample.json")
    inputs = read_json(output / "inputs_report.json")
    if digest(output / "sample.json") != inputs["outputs"]["sample.json"]:
        raise ValueError("Corrected sample changed")
    model = model_dir or base / "model"
    if not model.resolve().is_relative_to(base.resolve()):
        raise ValueError("The model input must stay inside this rebuild bundle")
    manifest = read_json(model / "manifest.json")
    for name, expected in manifest["outputs"].items():
        if digest(model / name) != expected:
            raise ValueError(f"Corrected model changed: {name}")
    source_hashes = {str(model / "manifest.json"): digest(model / "manifest.json")}
    records = read_json(base / "entities/full_records.json.gz")
    client = tools()
    client.CACHE = cache
    candidates = {}
    qids = {p["place_id"] for p in sample if p["wikidata_id"]}
    for source in client.OVERPASS:
        path = cache / f"first_50_{source.casefold()}.json"
        saved = read_json(path)
        if set(saved["qids"]) != qids:
            raise ValueError("Source request uses superseded sample QIDs")
        source_hashes[str(path)] = digest(path)
        candidates[source] = client.group_by_qid(saved["elements"], sorted(qids))

    # S2T 9: WHG uses names and the selection year. Reusing a response with
    # the same query does not restore the old QID used as its response key.
    old_whg = read_json(original / "whg_results.json")
    geonames_path = original / "geonames_candidates.json"
    geonames = read_json(geonames_path)
    source_hashes[str(geonames_path)] = digest(geonames_path)
    source_hashes[str(original / "whg_results.json")] = digest(
        original / "whg_results.json"
    )
    whg, missing = {}, []
    for place in sample:
        pid = place["place_id"]
        exact = sum(len(v.get(pid, [])) for v in candidates.values())
        if exact == 1 or not any(c.isalnum() for c in place["name"]):
            continue
        query = next(
            (
                q
                for q in old_whg["queries"]
                if q["name"] == place["name"]
                and q["related_dates"][0][:4] == place["selection_date"][:4]
            ),
            None,
        )
        if query:
            whg[pid] = old_whg["results"][query["qid"]]
        else:
            missing.append(
                dict(
                    qid=pid, name=place["name"], related_dates=[place["selection_date"]]
                )
            )
    if missing:
        fresh = cache / "sample_whg_fresh.json"
        if not fresh.exists():
            write(fresh, dict(queries=missing, results=client.reconcile_whg(missing)))
        saved = read_json(fresh)
        if saved["queries"] != missing:
            raise ValueError("WHG cache belongs to different input names/dates")
        whg.update(saved["results"])
        source_hashes[str(fresh)] = digest(fresh)

    accepted, audit = [], []
    for place in sample:
        pid = place["place_id"]
        row = dict(
            input=place,
            review_status="UNRESOLVED",
            geometry_ref=None,
            whg=whg.get(pid, []),
        )
        if not place["wikidata_id"]:
            # These frozen synthetic inputs have only Daniel's broad LOC type
            # and page references: no external ID, supported parent area, or
            # airport-code pair. A former QID's metadata is not input evidence.
            # S2T 9.1 forbids treating the page title as proof of a parent area.
            if place["wikidata_id"] is not None or any(
                c.get("subtype") != "LOC" for c in place["source_context"]
            ):
                raise SourceException(
                    "Synthetic sample context differs from the approved broad-LOC case",
                    place_id=pid,
                )
            paths = []
            for source, prefix in (
                ("OpenHistoricalMap", "ohm"),
                ("OpenStreetMap", "osm"),
            ):
                if not any(c.isalnum() for c in place["name"]):
                    continue
                previous = original / f"{prefix}_name_{place['previous_place_id']}.json"
                path = (
                    previous
                    if previous.exists()
                    else cache / f"{prefix}_name_{pid}.json"
                )
                if not path.exists():
                    params = dict(
                        q=place["name"],
                        format="jsonv2",
                        polygon_geojson="1",
                        extratags="1",
                        addressdetails="1",
                        namedetails="1",
                        limit="50",
                    )
                    url = client.NOMINATIM[source] + "/search"
                    write(
                        path,
                        dict(
                            source=url,
                            params=params,
                            retrieved_at=datetime.now(timezone.utc).isoformat(),
                            rows=client.request_json(url, params=params),
                        ),
                    )
                if read_json(path)["params"]["q"] != place["name"]:
                    raise ValueError("Name cache uses a different query")
                source_hashes[str(path)] = digest(path)
                paths.append(str(path))
            row.update(
                reason_code=(
                    "INSUFFICIENT_IDENTITY_EVIDENCE"
                    if paths
                    else "EMPTY_NORMALIZED_NAME"
                ),
                decision_reason="Name candidates do not supply the missing input identity evidence. No old QID, external-ID match flag or geometry decision is reused.",
                name_source_files=paths,
                # Preserve raw gazetteer records only. The old QID's external-ID
                # match boolean cannot establish a synthetic mention's identity.
                geonames_record_fields=[
                    r["fields"]
                    for r in geonames["results"].get(place["previous_place_id"], [])
                ],
            )
            audit.append(row)
            continue

        native = records[pid]["entity"]
        p31 = [
            s.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for s in native.get("claims", {}).get("P31", [])
        ]
        place_type = client.infer_place_type(
            dict(
                name=place["name"],
                text=native.get("descriptions", {}).get("en", {}).get("value", ""),
                attributes=dict(p31=p31),
            )
        )
        selected = None
        for source, grouped in candidates.items():
            candidate, reason = client.select_candidate(
                dict(place_type=place_type, selection_date=place["selection_date"]),
                grouped[pid],
            )
            if candidate is not None:
                if client.type_score(place_type, candidate) != 2:
                    raise SourceException(
                        "Exact-QID sample object has an unsupported feature meaning",
                        place_id=pid,
                    )
                selected = source, candidate, reason
                break
        if selected is None:
            raise SourceException(
                "Corrected sample QID has no supported source object", place_id=pid
            )
        source, candidate, reason = selected
        if candidate["type"] == "node":
            # A source node is already a complete point, not a computed centroid.
            geometry = Point(candidate["lon"], candidate["lat"])
        else:
            raw = client.cached_geometries(source, [candidate])
            value = raw[client.osm_key(candidate)]
            if (value.get("extratags") or {}).get("wikidata") != pid:
                raise SourceException("Geometry response QID differs", place_id=pid)
            geometry = client.geometry_from_row(value)
            path = cache / f"first_50_{source.casefold()}_geometries.json"
            source_hashes[str(path)] = digest(path)
        if geometry is None or geometry.is_empty or not geometry.is_valid:
            raise SourceException("Sample source geometry is invalid", place_id=pid)
        object_id = client.osm_key(candidate)
        url = (
            (
                "https://www.openhistoricalmap.org/"
                if source == "OpenHistoricalMap"
                else "https://www.openstreetmap.org/"
            )
            + candidate["type"]
            + "/"
            + str(candidate["id"])
        )
        accepted.append(
            dict(
                place_id=pid,
                name=place["name"],
                place_type=place_type,
                selection_date=place["selection_date"],
                source_dataset=source,
                source_object_id=object_id,
                source_url=url,
                match_method="EXACT_QID_DATE_TYPE",
                selection_policy_version="geo-object-selection-v0.5.0",
                retrieved_at=read_json(cache / f"first_50_{source.casefold()}.json")[
                    "retrieved_at"
                ],
                review_status="ACCEPTED_AUTO",
                decision_reason=reason,
                geometry=geometry,
            )
        )
        row.update(
            review_status="ACCEPTED_AUTO",
            source_dataset=source,
            source_object_id=object_id,
            decision_reason=reason,
        )
        audit.append(row)

    path = output / "geometries.parquet"
    if path.exists():
        raise ValueError("Preserve existing sample geometry artifact")
    frame = gpd.GeoDataFrame(accepted, geometry="geometry", crs="EPSG:4326")
    frame.to_parquet(path, index=False)
    geography_rows = []
    for row in audit:
        if row["review_status"] != "ACCEPTED_AUTO":
            continue
        pid = row["input"]["place_id"]
        pointer = dict(file=path.name, place_id=pid, sha256=digest(path))
        restored = load_geometry(pointer, output)
        if not restored.equals_exact(
            frame.loc[frame.place_id == pid].geometry.iloc[0], 0
        ):
            raise ValueError("Shapely round trip differs")
        row["geometry_ref"] = pointer
        record = next(r for r in accepted if r["place_id"] == pid)
        geography_rows.append(
            {k: v for k, v in record.items() if k not in {"geometry", "selection_date"}}
            | dict(geometry_ref=pointer)
        )
    write(output / "geography.json", geography_rows)
    report = dict(
        status="VERIFIED_CORRECTED_TEN_INPUT_GEOGRAPHY_SAMPLE",
        inputs=len(sample),
        accepted=len(accepted),
        unresolved=len(sample) - len(accepted),
        identity_assignments_changed=False,
        main_model_changed=False,
        final_graph_written=False,
        source_evidence=source_hashes,
        results=audit,
    )
    write(output / "audit.json", report)
    for name, expected in manifest["outputs"].items():
        if digest(model / name) != expected:
            raise ValueError("Corrected model changed during sample check")
    verification = dict(
        status=report["status"],
        inputs=len(sample),
        accepted=len(accepted),
        unresolved=report["unresolved"],
        geometry_roundtrip_exact=True,
        pointers_in_model_only=True,
        outputs={
            name: digest(output / name)
            for name in (
                "sample.json",
                "geography.json",
                "geometries.parquet",
                "audit.json",
            )
        },
    )
    write(output / "verification.json", verification)
    return verification


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.base, model_dir=args.model_dir), indent=2))
    except Exception as error:
        write(
            args.base / "geography_sample_failure.json",
            dict(
                status="STOPPED_FOR_CONSULTATION",
                error=f"{type(error).__name__}: {error}",
                case=getattr(error, "case", None),
            ),
        )
        raise

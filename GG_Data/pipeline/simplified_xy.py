"""Offline arbitrary-point overlay; no identity matching or source requests."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import math
import shutil
import time
import zipfile
from collections import Counter
from pathlib import Path

import ijson

from .poc import digest, read_json
from .simplified_agent import write_array, write_object

METHOD = "OWNER_ARBITRARY_FIRST_AVAILABLE"
EARTH = "http://www.wikidata.org/entity/Q2"


def valid_xy(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in value[:2]
        )
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def first_vertex(geometry: dict) -> list | None:
    """Keep native coordinate order; never calculate a centroid or mean."""
    if geometry.get("type") == "GeometryCollection":
        return next(
            (p for g in geometry.get("geometries", []) if (p := first_vertex(g))), None
        )
    if geometry.get("type") not in {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
    }:
        return None

    def visit(coordinates):
        if valid_xy(coordinates):
            return list(coordinates[:2])
        if isinstance(coordinates, (list, tuple)):
            for child in coordinates:
                if isinstance(child, (list, tuple)) and (point := visit(child)):
                    return point
        return None

    return visit(geometry.get("coordinates"))


def point_fields(xy: list) -> dict:
    return dict(
        status="SOURCE_POINT_SELECTED_ARBITRARILY",
        x=xy[0],
        y=xy[1],
        geometry=dict(type="Point", coordinates=xy),
        crs="EPSG:4326",
        selection_method=METHOD,
        identity_verified=False,
    )


def choose_loc(result: dict) -> dict | None:
    for candidate in sorted(
        result["ranking"], key=lambda c: (c["source"], c["source_id"])
    ):
        geometry = candidate.get("geometry")
        if not candidate.get("geometry_available") or not geometry:
            continue
        xy = first_vertex(geometry)
        if xy is not None:
            return dict(
                **point_fields(xy),
                source=candidate["source"],
                source_object_id=candidate["source_id"],
                source_reference=candidate.get("receipt"),
                source_geometry=geometry,
                coordinate_method=(
                    "NATIVE_SOURCE_POINT"
                    if geometry["type"] == "Point"
                    else "FIRST_SOURCE_GEOMETRY_VERTEX"
                ),
                source_uncertainty_flags=candidate.get("uncertainty_flags", []),
                source_score_not_probability=candidate.get("total"),
            )
    return None


def choose_event(record: dict) -> dict | None:
    statements = record.get("claims", {}).get("P625", [])
    valid = []
    for statement in statements:
        value = statement.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        xy = [value.get("longitude"), value.get("latitude")]
        if (
            statement.get("rank") != "deprecated"
            and value.get("globe") == EARTH
            and valid_xy(xy)
        ):
            valid.append((statement, xy))
    if not valid:
        return None
    statement, xy = min(valid, key=lambda pair: pair[0].get("id", ""))
    return dict(
        **point_fields(xy),
        source="Wikidata",
        source_object_id=statement.get("id"),
        coordinate_method="NATIVE_EARTH_P625_STATEMENT",
        chosen_statement=statement,
        native_coordinate_statements=statements,
        valid_coordinate_alternatives=len(valid),
        arbitrary_among_multiple=len(valid) > 1,
    )


def build(model: Path, ranking: Path, native: Path, output: Path) -> dict:
    """Account for every corrected LOC/Event, without modifying the core."""
    if output.exists():
        raise FileExistsError(output)
    manifest = read_json(model / "manifest.json")
    inputs = {str((model / "manifest.json").resolve()): digest(model / "manifest.json")}
    for name in [
        "entities.json.gz",
        "event_events.json.gz",
        "entity_exclusions.json.gz",
    ]:
        path = model / name
        sha = digest(path)
        if manifest["outputs"][name] != sha:
            raise ValueError(f"Corrected core checksum mismatch: {name}")
        inputs[str(path.resolve())] = sha
    receipt_path = ranking / "verification.json"
    receipt = read_json(receipt_path)
    if receipt["status"] != "VERIFIED_RANKING_PROPOSALS":
        raise ValueError("Cached geography batch is not verified")
    inputs[str(receipt_path.resolve())] = digest(receipt_path)
    for name, expected in receipt["outputs"].items():
        path = ranking / name
        if digest(path) != expected:
            raise ValueError(f"Cached geography checksum mismatch: {name}")
    audit_path = ranking / "audit.json"
    inputs[str(audit_path.resolve())] = digest(audit_path)
    native_sha = digest(native)
    pinned = [
        r["sha256"]
        for r in manifest.get("correction_inputs", [])
        if Path(r["path"]).resolve() == native.resolve()
    ]
    if pinned and pinned != [native_sha]:
        raise ValueError("Native Event evidence differs from corrected core")
    inputs[str(native.resolve())] = native_sha
    with gzip.open(model / "entities.json.gz", "rb") as stream:
        entities = {
            r["entity_id"]: {k: r[k] for k in ["entity_id", "name", "type"]}
            for r in ijson.items(stream, "item", use_float=True)
            if r["type"] in {"LOC", "event"}
        }
    events = {r["entity_id"]: r for r in read_json(model / "event_events.json.gz")}
    if set(events) != {k for k, r in entities.items() if r["type"] == "event"}:
        raise ValueError("Corrected Event IDs differ from entities")
    qids = {}
    for key, event in events.items():
        native_ids = {r["qid"] for r in event["native_records"]}
        if len(native_ids) != 1 or key != "event:" + next(iter(native_ids)):
            raise ValueError("Event must retain its exact native QID")
        qids[key] = next(iter(native_ids))
    excluded = {r["entity_id"] for r in read_json(model / "entity_exclusions.json.gz")}
    results = read_json(audit_path)["results"]
    if len(results) != receipt["inputs"]:
        raise ValueError("Cached geography denominator changed")
    loc_results, stale = {}, []
    for result in results:
        key = result["input"]["place_id"]
        if key in loc_results or key in stale:
            raise ValueError("Duplicate cached exact LOC key")
        if key not in entities:
            if key not in excluded:
                raise ValueError("Unknown cached LOC ID is not a recorded exclusion")
            stale.append(key)
            continue
        if entities[key]["type"] != "LOC":
            raise ValueError("Cached LOC ID changed type")
        loc_results[key] = result
    native_records = {}
    with native.open("rb") as stream:
        for qid, record in ijson.kvitems(stream, "", use_float=True):
            if qid in qids.values():
                native_records[qid] = record
    if set(native_records) != set(qids.values()):
        raise ValueError("Corrected Event is missing its native evidence")
    rows = []
    for key, entity in sorted(entities.items()):
        row = dict(
            entity,
            status="NO_SAVED_COORDINATE",
            x=None,
            y=None,
            geometry=None,
            crs=None,
            identity_verified=False,
            selection_method=None,
        )
        if entity["type"] == "event":
            record = native_records[qids[key]]
            row.update(
                status="NO_SOURCE_COORDINATE",
                source="Wikidata",
                source_reference=str(native.resolve()) + "#" + qids[key],
                native_coordinate_statements=record.get("claims", {}).get("P625", []),
            )
            row.update(choose_event(record) or {})
        elif key in loc_results:
            row.update(
                status="NO_SOURCE_COORDINATE",
                source_evidence=dict(
                    path=str(audit_path.resolve()),
                    sha256=inputs[str(audit_path.resolve())],
                    exact_place_id=key,
                ),
            )
            row.update(choose_loc(loc_results[key]) or {})
        rows.append(row)
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError(f"Input changed during offline selection: {path}")
    output.mkdir(parents=True)
    overlay = output / "xy_overlay.json.gz"
    write_array(overlay, rows)
    restored = read_json(overlay)
    if len(restored) != len(entities) or {r["entity_id"] for r in restored} != set(
        entities
    ):
        raise ValueError("Overlay exact-ID coverage differs from corrected core")
    for row in restored:
        if row["geometry"] is not None:
            if not valid_xy([row["x"], row["y"]]) or row["geometry"] != dict(
                type="Point", coordinates=[row["x"], row["y"]]
            ):
                raise ValueError("Invalid output point")
        elif row["x"] is not None or row["y"] is not None:
            raise ValueError("Missing source must not receive invented coordinates")
    report = dict(
        status="OFFLINE_XY_TRIAL_COMPLETE_NOT_INTEGRATED",
        selection_method=METHOD,
        identity_assignments_added=0,
        identities_verified=0,
        network_requests=0,
        core_model_manifest_sha256=inputs[str((model / "manifest.json").resolve())],
        scope="ALL_CORRECTED_LOC_AND_EVENTS_ACCOUNTED; ONLY_FIRST_SAVED_250_LOC_LOOKED_UP",
        counts={
            label: dict(Counter(r["status"] for r in rows if r["type"] == kind))
            for label, kind in [("LOC", "LOC"), ("EVENT", "event")]
        },
        total_rows=len(rows),
        cached_loc_inputs=len(results),
        retained_cached_loc_inputs=len(loc_results),
        excluded_cached_loc_ids=sorted(stale),
        inputs=inputs,
        code_sha256=digest(Path(__file__)),
        outputs={overlay.name: digest(overlay)},
        coordinate_methods=dict(
            Counter(r.get("coordinate_method", "NO_COORDINATE") for r in rows)
        ),
        caveat="Arbitrary source coordinates are not verified identities, exact historical extents, or confidence estimates.",
    )
    write_object(output / "manifest.json", report)
    write_object(
        output / "verification.json",
        dict(
            status="VERIFIED_OFFLINE_OVERLAY_IDS_COORDINATES_AND_INPUT_HASHES",
            rows=len(restored),
            core_unchanged=True,
            overlay_sha256=digest(overlay),
            manifest_sha256=digest(output / "manifest.json"),
            checks=[
                "EXACT_CORRECTED_IDS",
                "SOURCE_HASHES",
                "FINITE_EARTH_BOUNDS",
                "NO_INVENTED_MISSING_POINTS",
            ],
        ),
    )
    return report


def normalize_name(value: str) -> str:
    """Only case folding and whitespace normalization; no fuzzy matching."""
    return " ".join(value.casefold().split())


def exact_geonames(requested: set[str], archives: list[Path]) -> tuple[dict, dict]:
    """One streaming pass; keep one winner and distinct native IDs per name."""
    matches, seen = {}, {}
    report = dict(
        rows_scanned=0,
        malformed_rows=0,
        invalid_matching_coordinate_rows=0,
        archive_hashes={},
        largest_distinct_candidate_set=0,
    )
    started = time.perf_counter()
    for archive in sorted(archives):
        sha = digest(archive)
        report["archive_hashes"][str(archive.resolve())] = sha
        with zipfile.ZipFile(archive) as zipped:
            member = archive.stem + ".txt"
            with zipped.open(member) as binary, io.TextIOWrapper(
                binary, encoding="utf-8", newline=""
            ) as stream:
                for number, fields in enumerate(
                    csv.reader(stream, delimiter="\t", quoting=csv.QUOTE_NONE), 1
                ):
                    report["rows_scanned"] += 1
                    if len(fields) != 19 or not fields[0].isdigit():
                        report["malformed_rows"] += 1
                        continue
                    names = {}
                    for field, values in [
                        ("name", [fields[1]]),
                        ("asciiname", [fields[2]]),
                        ("alternatenames", fields[3].split(",")),
                    ]:
                        for value in values:
                            key = normalize_name(value)
                            if key and key in requested:
                                names.setdefault(key, (field, value))
                    if not names:
                        continue
                    try:
                        xy = [float(fields[5]), float(fields[4])]
                    except ValueError:
                        xy = []
                    if not valid_xy(xy):
                        report["invalid_matching_coordinate_rows"] += 1
                        continue
                    for key, (field, value) in names.items():
                        seen.setdefault(key, set()).add(fields[0])
                        if key not in matches:
                            matches[key] = dict(
                                **point_fields(xy),
                                source="GeoNames",
                                source_object_id=fields[0],
                                coordinate_method="LOCAL_GEONAMES_EXACT_NAME_POINT",
                                lookup_method="EXACT_CASEFOLD_WHITESPACE_NAME_ASCII_OR_ALIAS",
                                matched_name_field=field,
                                matched_source_name=value,
                                normalized_lookup_name=key,
                                native_row=fields,
                                source_archive=str(archive.resolve()),
                                source_archive_sha256=sha,
                                source_member=member,
                                source_row_number=number,
                                source_reference=str(archive.resolve())
                                + "!"
                                + member
                                + ":"
                                + str(number),
                            )
        if digest(archive) != sha:
            raise ValueError("GeoNames source changed during its single pass")
    for key, match in matches.items():
        match["distinct_native_candidates"] = len(seen[key])
        match["arbitrary_among_multiple"] = len(seen[key]) > 1
    report.update(
        matched_normalized_names=len(matches),
        requested_normalized_names=len(requested),
        largest_distinct_candidate_set=max(map(len, seen.values()), default=0),
        elapsed_seconds=time.perf_counter() - started,
    )
    return matches, report


def extend_local(prior: Path, model: Path, archives: Path, output: Path) -> dict:
    """Keep all v1 points; fill missing LOCs only from existing local archives."""
    if output.exists():
        raise FileExistsError(output)
    if shutil.disk_usage(output.parent).free < 17 * 1024**3:
        raise OSError("15 GiB free reserve plus 2 GiB output allowance required")
    previous = read_json(prior / "manifest.json")
    verified = read_json(prior / "verification.json")
    inputs = dict(previous["inputs"])
    if digest(model / "manifest.json") != previous["core_model_manifest_sha256"]:
        raise ValueError(
            "Corrected core manifest differs from the verified prior overlay"
        )
    if digest(prior / "manifest.json") != verified["manifest_sha256"]:
        raise ValueError("Prior overlay manifest checksum mismatch")
    for name, expected in previous["outputs"].items():
        if digest(prior / name) != expected:
            raise ValueError("Prior overlay checksum mismatch")
    for path in [
        prior / "manifest.json",
        prior / "verification.json",
        prior / "xy_overlay.json.gz",
        model / "manifest.json",
    ]:
        inputs[str(path.resolve())] = digest(path)
    if digest(prior / "xy_overlay.json.gz") != verified["overlay_sha256"]:
        raise ValueError("Prior overlay verification binding differs")
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError("Prior source evidence changed")
    rows = read_json(prior / "xy_overlay.json.gz")
    identifiers = [r["entity_id"] for r in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate prior overlay entity ID")
    requested = {
        normalize_name(r["name"])
        for r in rows
        if r["type"] == "LOC" and r["geometry"] is None
    }
    files = sorted(archives.glob("*.zip"))
    if not files:
        raise ValueError("No existing GeoNames archives")
    matches, scan = exact_geonames(requested - {""}, files)
    inputs.update(scan["archive_hashes"])
    extended, added = [], 0
    for row in rows:
        if row["type"] == "LOC" and row["geometry"] is None:
            match = matches.get(normalize_name(row["name"]))
            if match:
                row = dict(row, **match)
                added += 1
            else:
                row = dict(row, status="NO_LOCAL_EXACT_SOURCE_COORDINATE")
        extended.append(row)
    for before, after in zip(rows, extended):
        if before["geometry"] is not None or before["type"] != "LOC":
            if before != after:
                raise ValueError("An existing point or Event row changed")
        if after["geometry"] is not None and not valid_xy([after["x"], after["y"]]):
            raise ValueError("Invalid source coordinate in extended overlay")
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError("Source changed during local extension")
    output.mkdir(parents=True)
    overlay = output / "xy_overlay.json.gz"
    write_array(overlay, extended)
    restored = read_json(overlay)
    if [r["entity_id"] for r in restored] != identifiers or restored != extended:
        raise ValueError("Serialized overlay changed IDs or rows")
    report = dict(
        status="OFFLINE_LOCAL_XY_EXTENSION_COMPLETE_NOT_INTEGRATED",
        selection_method=METHOD,
        core_model_manifest_sha256=previous["core_model_manifest_sha256"],
        identity_assignments_added=0,
        identities_verified=0,
        network_requests=0,
        scope="ALL_CORRECTED_LOC_AND_EVENTS; EXISTING_POINTS_PRESERVED; LOCAL_EXACT_NAMES_ONLY",
        total_rows=len(restored),
        new_loc_points=added,
        existing_rows_preserved=True,
        counts={
            label: dict(Counter(r["status"] for r in restored if r["type"] == kind))
            for label, kind in [("LOC", "LOC"), ("EVENT", "event")]
        },
        source_scan=scan,
        inputs=inputs,
        code_sha256=digest(Path(__file__)),
        outputs={overlay.name: digest(overlay)},
        normalization="CASEFOLD_AND_WHITESPACE_ONLY",
        selection_order="SORTED_ARCHIVE_THEN_COUNTRY_MEMBER_NATIVE_ROW_ORDER; DISTINCT_NATIVE_ID_COUNTS",
        caveat="Available country archives are incomplete. Exact names and arbitrary points do not establish identity or historical extent.",
    )
    write_object(output / "manifest.json", report)
    write_object(
        output / "verification.json",
        dict(
            status="VERIFIED_LOCAL_OVERLAY_IDS_SOURCE_HASHES_AND_PRESERVED_ROWS",
            rows=len(restored),
            existing_rows_preserved=True,
            core_unchanged=True,
            overlay_sha256=digest(overlay),
            manifest_sha256=digest(output / "manifest.json"),
        ),
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ["model", "output"]:
        parser.add_argument("--" + argument, type=Path, required=True)
    for argument in ["ranking", "native", "prior", "archives"]:
        parser.add_argument("--" + argument, type=Path)
    args = parser.parse_args()
    if args.prior and args.archives:
        report = extend_local(args.prior, args.model, args.archives, args.output)
    elif args.ranking and args.native and not (args.prior or args.archives):
        report = build(args.model, args.ranking, args.native, args.output)
    else:
        parser.error("Use --prior/--archives or --ranking/--native")
    print(report["status"], report["counts"])

"""Populate Geography from the existing S2T 9.7 retrieval and ranking stages.

No new identity or geometry algorithm lives here. The wrapper changes the
denominator from the frozen tests to every LOC row of the new 10K model, then
stores the selected source geometries and model-only Shapely file references.
Each phase is explicit so a source/data failure stops before the next phase.
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
from collections import Counter
from pathlib import Path

import geopandas as gpd

from . import geography_comparison, geography_ranking_sample, osm_bigquery
from .entities import acquire_missing, full_records
from .poc import ROOT, digest, read_json
from .rebuild_poc import write


def candidate_records(base: Path, comparison: Path) -> dict:
    """S2T 1/9.3: fetch same-QID native records, never add Entity rows.

    Only synthetic inputs need candidate-only Wikidata coordinates. Matched
    inputs already have their selected whole snapshot record in Entities.
    Name candidates use the existing >=80% trigram criterion. A candidate's
    coordinate remains a labelled hypothesis, not a new identity assignment.
    """
    if (comparison / "candidate_records.json.gz").exists():
        raise ValueError("Preserve completed Geography candidate records")
    if read_json(comparison / "progress.json")["status"] != "RETRIEVED":
        raise ValueError("Complete source retrieval before coordinate acquisition")
    targets = read_json(comparison / "sample.json")
    responses = [
        read_json(comparison / f"sources/whg_{arm}.json")["response"]
        for arm in ("native", "existing_dated")
    ]
    wanted = {
        c["id"].split(":")[-1]
        for p in targets
        if not p["wikidata_id"]
        for response in responses
        for c in response.get(p["place_id"], {}).get("result", [])
        if c["id"].startswith("place:wd:")
        and max(
            (
                geography_ranking_sample.similarity(p["name"], n)
                for n in [c["name"], *c.get("alt_names", [])]
            ),
            default=0,
        )
        >= 0.8
    }
    own = read_json(base / "entities/full_records.json.gz")
    records = {q: own[q] for q in wanted & own.keys()}
    missing = wanted - records.keys()
    provenance = {}
    if missing:
        archive = ROOT / "Data/external/wwii_task_force/wikidata_entities.jsonl.gz"
        archived, sources = full_records(missing, archive)
        available = {q: [(r, sources[q])] for q, r in archived.items()}
        reference = read_json(base / "matching/reference_manifest.json")
        acquired, provenance = acquire_missing(
            missing,
            ROOT / "GG_Data/pipeline/outputs/wikidata_full_cache",
            reference,
            available_records=available,
        )
        records.update(acquired)
    if set(records) != wanted:
        raise ValueError("Candidate coordinate records do not cover requested QIDs")
    path = comparison / "candidate_records.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, allow_nan=False)
    report = dict(
        status="SNAPSHOT_FIRST_GEOGRAPHY_CANDIDATE_RECORDS",
        candidate_qids=len(wanted),
        identities_added=0,
        provenance=provenance,
        inputs={
            str(p): digest(p)
            for p in (
                base / "entities/full_records.json.gz",
                comparison / "sample.json",
                *(
                    comparison / f"sources/whg_{a}.json"
                    for a in ("native", "existing_dated")
                ),
            )
        },
        outputs={path.name: digest(path)},
    )
    write(comparison / "candidate_records_report.json", report)
    return report


def source_url(chosen: dict) -> str | None:
    """Project native source IDs; no search result becomes an invented ID."""
    source, sid = chosen["source"], chosen["source_id"]
    if source == "Wikidata":
        return "https://www.wikidata.org/wiki/" + chosen["qid"]
    if source == "GeoNames":
        return "https://www.geonames.org/" + sid
    if source in {"OpenStreetMap", "OpenHistoricalMap"}:
        kind, number = sid.split(":", 1)
        domain = (
            "openstreetmap.org"
            if source == "OpenStreetMap"
            else "openhistoricalmap.org"
        )
        return f"https://www.{domain}/{kind}/{number}"
    return None


def populate(base: Path, ranked: Path, output: Path) -> dict:
    """S2T 9/ERD: one selected object per LOC; references stay in the model.

    Preserve all existing physical tables byte for byte. The 13-column
    GeoParquet view contains native shapes; checksum references stay outside
    the artifact they identify. Uncertainty is audit evidence, not a veto.
    """
    if output.exists():
        raise ValueError("Preserve earlier model versions")
    verification = read_json(ranked / "verification.json")
    for name, sha in verification["outputs"].items():
        if digest(ranked / name) != sha:
            raise ValueError(f"Ranked Geography output changed: {name}")
    model = base / "model"
    manifest = read_json(model / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(model / name) != sha:
            raise ValueError(f"Model table changed: {name}")
    places = {
        r["entity_id"]
        for r in read_json(model / "entities.json.gz")
        if r["type"] == "LOC"
    }
    audit = read_json(ranked / "audit.json")
    results = audit["results"]
    if {r["input"]["place_id"] for r in results} != places or len(results) != len(
        places
    ):
        raise ValueError("Geography denominator differs from all model LOC rows")
    shapes = gpd.read_parquet(ranked / "proposed_geometries.parquet")
    if shapes.crs is None or shapes.place_id.duplicated().any():
        raise ValueError("Selected geometry metadata is missing or duplicated")
    by_id = dict(zip(shapes.place_id, shapes.geometry))
    rows, geometry_rows = [], []
    for row in results:
        place, chosen = row["input"], row["proposed"]
        pid = place["place_id"]
        available = any(c["geometry_available"] for c in row["ranking"])
        if bool(chosen) != available:
            raise ValueError(f"Available geometry left unresolved: {pid}")
        if chosen is None:
            if pid in by_id:
                raise ValueError("Unresolved place has an unreported selected shape")
            continue
        geometry = by_id[pid]
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid selected geometry: {pid}")
        # Preserve original request time where supplied, not this export time.
        receipt = Path(chosen["receipt"])
        retrieved_at = None
        if receipt.is_file() and receipt.suffix == ".json":
            retrieved_at = read_json(receipt).get("retrieved_at")
        reason = json.dumps(
            dict(
                components=chosen["components"],
                uncertainty_flags=chosen["uncertainty_flags"],
                source_receipt=chosen["receipt"],
                identity_assignments_changed=False,
            ),
            ensure_ascii=False,
        )
        record = dict(
            place_id=pid,
            name=place["name"],
            place_type=place["type"],
            source_dataset=chosen["source"],
            source_object_id=chosen["source_id"],
            source_url=source_url(chosen),
            match_method="WEIGHTED_CONTEXT_RANKING",
            selection_policy_version=geography_ranking_sample.PARAMETERS["version"],
            retrieved_at=retrieved_at,
            review_status="ACCEPTED_AUTO",
            decision_reason=reason,
        )
        rows.append(record)
        geometry_rows.append(
            record | dict(selection_date=place["selection_date"], geometry=geometry)
        )
    if set(by_id) != {r["place_id"] for r in rows}:
        raise ValueError("Selected shape and model pointer populations differ")
    output.mkdir(parents=True)
    path = output / "geometries.parquet"
    frame = gpd.GeoDataFrame(geometry_rows, geometry="geometry", crs=shapes.crs)
    # Exact legacy column order is part of the ERD compatibility contract.
    frame = frame[
        [
            "place_id",
            "name",
            "place_type",
            "selection_date",
            "source_dataset",
            "source_object_id",
            "source_url",
            "match_method",
            "selection_policy_version",
            "retrieved_at",
            "review_status",
            "decision_reason",
            "geometry",
        ]
    ]
    frame.to_parquet(path, index=False)
    restored = gpd.read_parquet(path)
    if len(frame) != len(restored) or not all(
        a.equals_exact(b, 0) for a, b in zip(frame.geometry, restored.geometry)
    ):
        raise ValueError("Geography Shapely/WKB round trip differs")
    sha = digest(path)
    for row in rows:
        row["geometry_ref"] = dict(file=path.name, place_id=row["place_id"], sha256=sha)
    with gzip.open(output / "geography.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False, allow_nan=False)
    for name in manifest["outputs"]:
        shutil.copyfile(model / name, output / name)
    report = dict(
        **{
            k: v
            for k, v in manifest.items()
            if k not in {"status", "inputs", "outputs", "pending_stages"}
        },
        status="MODEL_WITH_RANKED_GEOGRAPHY",
        geography_targets=len(places),
        geography_rows=len(rows),
        unresolved_geography=len(places) - len(rows),
        selected_sources=dict(Counter(r["source_dataset"] for r in rows)),
        pointers_in_model_only=True,
        identity_assignments_changed=False,
        pending_stages=["graph", "Agent"],
        inputs={
            **manifest["inputs"],
            str(model / "manifest.json"): digest(model / "manifest.json"),
            str(ranked / "verification.json"): digest(ranked / "verification.json"),
        },
        outputs={p.name: digest(p) for p in output.iterdir() if p.is_file()},
    )
    write(output / "manifest.json", report)
    write(
        output / "verification.json",
        dict(
            status="VERIFIED_MODEL_WITH_RANKED_GEOGRAPHY",
            manifest_sha256=digest(output / "manifest.json"),
            geometry_roundtrip_exact=True,
            accepted=len(rows),
            unresolved=len(places) - len(rows),
            all_previous_tables_unchanged=all(
                digest(output / name) == sha
                for name, sha in manifest["outputs"].items()
            ),
            pointers_in_model_only=True,
        ),
    )
    return report


def run(phase: str, base: Path) -> dict:
    comparison = base / "geography_retrieval"
    if phase == "prepare":
        return geography_comparison.prepare(
            base, comparison, all_targets=True, model_dir=base / "model"
        )
    if phase == "retrieve":
        return geography_comparison.retrieve(comparison)
    if phase == "osm-bigquery":
        return osm_bigquery.retrieve(base)
    if phase == "records":
        return candidate_records(base, comparison)
    if phase == "rank":
        return geography_ranking_sample.run(
            base / "geography_ranked", comparison=comparison, base_dir=base
        )
    if phase == "populate":
        return populate(base, base / "geography_ranked", base / "model_geography")
    raise ValueError(f"Unknown Geography phase: {phase}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=("prepare", "osm-bigquery", "retrieve", "records", "rank", "populate"),
    )
    parser.add_argument("--base", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.phase, args.base), ensure_ascii=True))
    except Exception as exc:
        write(
            args.base / "geography_failure.json",
            dict(
                status="STOPPED_FOR_CONSULTATION",
                phase=args.phase,
                error=f"{type(exc).__name__}: {exc}",
                case=getattr(exc, "case", None),
            ),
        )
        raise

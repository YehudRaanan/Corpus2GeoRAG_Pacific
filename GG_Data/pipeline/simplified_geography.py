"""Use the existing Geography retrieval and ranking with exact name/type IDs."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from .geography import selection_value
from .poc import digest, read_json
from .simplified_agent import entity_id, write_array, write_object

LOG = logging.getLogger(__name__)


def bundle_geography_evidence(base: Path, output: Path) -> dict:
    """Portable exact-byte receipts and audits; no settings or archive copies."""
    count = 0

    def artifacts():
        nonlocal count
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(base)
            if (
                not path.is_file()
                or relative.parts[0] == "model"
                or not path.name.endswith(
                    (".json", ".json.gz", ".response", ".csv", ".txt")
                )
            ):
                continue
            sha = digest(path)
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != sha or digest(path) != sha:
                raise ValueError("Geography evidence changed during packaging")
            count += 1
            yield dict(
                original_path=str(path.resolve()),
                artifact_path="geography_work/" + relative.as_posix(),
                sha256=sha,
                encoding="base64",
                content_base64=base64.b64encode(content).decode("ascii"),
            )

    write_array(output, artifacts())
    return dict(
        artifact_count=count,
        sha256=digest(output),
        format="geography-evidence-base64-v1",
    )


def complete_geography(
    model: Path,
    core_graph: Path,
    core_release: Path,
    prepared: Path,
    output: Path,
    metadata: Path,
    agent_python: Path,
    source_project: Path,
) -> dict:
    """Run the last population phase and publish a new, fully checked release."""
    from .poc import ROOT
    from .simplified_verify import verify_and_package

    (
        model,
        core_graph,
        core_release,
        prepared,
        output,
        metadata,
        agent_python,
        source_project,
    ) = (
        p.resolve()
        for p in (
            model,
            core_graph,
            core_release,
            prepared,
            output,
            metadata,
            agent_python,
            source_project,
        )
    )
    if output.exists():
        raise FileExistsError(output)
    if not agent_python.is_file():
        raise FileNotFoundError("Existing Agent Python environment is required")
    output.mkdir()
    base = output / "geography_work"
    prepare_geography(model, core_release, base)
    configure_sources(base, source_project)
    run_population(base, metadata)
    geography = output / "geography.json.gz"
    aggregate_geography(base, geography)
    enriched_model, enriched_graph = output / "model", output / "graph"
    populate_geography(model, core_graph, geography, enriched_model, enriched_graph)
    subprocess.run(
        [
            str(agent_python),
            "-m",
            "geo_agent.verify_compact",
            str((enriched_graph / "agent_graph.json.gz").resolve()),
            str((enriched_graph / "agent_acceptance.json").resolve()),
        ],
        cwd=ROOT / "Agent",
        check=True,
    )
    return verify_and_package(
        prepared, enriched_model, enriched_graph, output / "release"
    )


def configure_sources(base: Path, source_project: Path) -> dict:
    """Reuse the existing scoped credential accessor and original source caches."""
    import importlib

    from .geography_sample import tools
    from .poc import ROOT

    client = tools()
    legacy = importlib.import_module("GEO_OBJECT_EXTRACTION_POC")
    setting = source_project / ".env"
    if not setting.is_file():
        raise FileNotFoundError("Existing WHG service setting file is required")
    # Do not copy, display or read other settings. The established accessor
    # reads only the WHG setting at the actual request stage.
    legacy.ENV_FILE = setting.resolve()
    archives = ROOT / "GG_Data/geocoding/cache/geonames"
    archives.mkdir(parents=True, exist_ok=True)
    evidence = {}
    for path in sorted(
        (source_project / "GG_Data/geocoding/cache/geonames").glob("*.zip")
    ):
        sha = digest(path)
        destination = archives / path.name
        if not destination.exists():
            os.link(path, destination)
        if digest(destination) != sha or digest(path) != sha:
            raise ValueError("Native GeoNames cache changed")
        evidence[str(path.resolve())] = sha
    cache = base / "response_cache/sources"
    cache.mkdir(parents=True, exist_ok=True)
    count = 0
    for folder in sorted(
        (source_project / "GG_Data/pipeline/outputs").glob("geography*")
    ):
        for path in sorted(folder.rglob("*.json")):
            if path.parent.name != "sources":
                continue
            saved = read_json(path)
            if (
                not isinstance(saved, dict)
                or not {"url", "params", "response"} <= saved.keys()
            ):
                continue
            if not any(
                saved["url"].startswith(endpoint + "/")
                for endpoint in client.NOMINATIM.values()
            ):
                continue
            sha = digest(path)
            destination = cache / (sha + ".json")
            if not destination.exists():
                os.link(path, destination)
                count += 1
            if digest(destination) != sha or digest(path) != sha:
                raise ValueError("Original exact-request cache changed")
            evidence[str(path.resolve())] = sha
    result = dict(
        status="EXISTING_SOURCE_CACHES_READY",
        new_source_requests=0,
        raw_response_files_added=count,
        service_setting_path=str(setting.resolve()),
        identities_imported=0,
        original_source_sha256=evidence,
    )
    write_object(base / "source_cache_manifest.json", result)
    return result


def run_population(base: Path, metadata: Path, *, batch_size: int = 250) -> dict:
    """One sequential owner; completed batches resume, failed attempts stop."""
    import msvcrt

    # Windows releases this byte lock if the worker exits. Retain the file as
    # evidence; incomplete batch directories still require explicit review.
    with (base / "worker.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            return _run_population(base, metadata, batch_size=batch_size)
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _run_population(base: Path, metadata: Path, *, batch_size: int) -> dict:
    from . import geography_comparison, geography_ranking_sample
    from .geography_sample import tools
    from .rebuild_poc import write
    from .simplified_page_events import PageEvidenceClient

    report = read_json(base / "geography_inputs/report.json")
    for name, sha in report["outputs"].items():
        if digest(base / name) != sha:
            raise ValueError(f"Changed Geography preparation: {name}")
    targets = read_json(base / "geography_inputs/targets.json")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("Invalid Geography batch size")
    cache = base / "response_cache"
    (cache / "sources").mkdir(parents=True, exist_ok=True)
    progress = dict(
        status="RUNNING",
        total_ready_targets=len(targets),
        completed_targets=0,
        failed_input_targets=report["failed_input_targets"],
        pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(),
    )
    try:
        for start in range(0, len(targets), batch_size):
            if shutil.disk_usage(base).free < 17 * 1024**3:
                raise OSError(
                    "Stop before the next Geography batch: 15 GiB reserve plus 2 GiB batch allowance required"
                )
            folder = base / "batches" / f"{start:06d}"
            ranking = folder / "ranking"
            verification = ranking / "verification.json"
            if verification.exists():
                saved = read_json(verification)
                if saved["status"] != "VERIFIED_RANKING_PROPOSALS":
                    raise ValueError("Previous batch is not verified")
                for name, sha in saved["outputs"].items():
                    if digest(ranking / name) != sha:
                        raise ValueError("Previous batch artifact changed")
                expected = targets[start : start + batch_size]
                if read_json(ranking / "sample.json") != expected:
                    raise ValueError("Previous batch scope changed")
            else:
                if folder.exists():
                    raise ValueError(
                        f"Incomplete batch requires review before resume: {folder}"
                    )
                progress.update(current_start=start, phase="PREPARE_BATCH")
                write(base / "progress.json", progress)
                folder = prepare_batch(base, start, batch_size)
                comparison = folder / "retrieval"
                progress["phase"] = "RETRIEVE_WHG"
                write(base / "progress.json", progress)
                retrieved = geography_comparison.retrieve(comparison)
                if retrieved["status"] != "RETRIEVED":
                    raise RuntimeError(
                        f"Source retrieval stopped: {retrieved.get('error_type')}: {retrieved.get('error')}"
                    )
                progress["phase"] = "CANDIDATE_COORDINATE_EVIDENCE"
                write(base / "progress.json", progress)
                client = PageEvidenceClient(
                    folder / "native_requests",
                    allow_api=True,
                    deadline=time.monotonic() + 3600,
                    max_requests=1000,
                    min_interval=1,
                )
                candidate_records(comparison, metadata, client)
                progress["phase"] = "EXISTING_GEOGRAPHY_RANKING"
                write(base / "progress.json", progress)
                with slow_nominatim(tools(), base / "nominatim_pacing.json"):
                    geography_ranking_sample.run(
                        ranking, cache, comparison, base_dir=base
                    )
            # Reuse only original endpoint/parameter responses in later batches.
            # No old entity assignments, selected geometries or name joins.
            for path in (ranking / "sources").glob("*.json"):
                destination = cache / "sources" / path.name
                if destination.exists():
                    a, b = read_json(path), read_json(destination)
                    if any(a[k] != b[k] for k in ("url", "params", "response")):
                        raise ValueError("Conflicting exact-request cache receipts")
                else:
                    os.link(path, destination)
            progress.update(
                completed_targets=min(start + batch_size, len(targets)),
                phase="BATCH_VERIFIED",
            )
            write(base / "progress.json", progress)
            LOG.info(
                "Geography targets verified %s/%s",
                progress["completed_targets"],
                len(targets),
            )
        progress.update(status="COMPLETE", phase="ALL_BATCHES_VERIFIED")
    except Exception as exc:
        progress.update(
            status="STOPPED_REQUIRES_REVIEW",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        write(base / "progress.json", progress)
        raise
    write(base / "progress.json", progress)
    return progress


def aggregate_geography(base: Path, output: Path) -> dict:
    """Account for every LOC once, using only completed, hash-verified batches."""
    if output.exists():
        raise FileExistsError(output)
    report = read_json(base / "geography_inputs/report.json")
    targets = read_json(base / "geography_inputs/targets.json")
    expected = {p["place_id"]: p for p in targets}
    rows = {}
    for verification in sorted(base.glob("batches/*/ranking/verification.json")):
        folder = verification.parent
        checked = read_json(verification)
        if checked["status"] != "VERIFIED_RANKING_PROPOSALS":
            raise ValueError("Unverified Geography batch")
        for name, sha in checked["outputs"].items():
            if digest(folder / name) != sha:
                raise ValueError(f"Changed Geography batch artifact: {folder / name}")
        results = read_json(folder / "audit.json")["results"]
        if len(results) != checked["inputs"]:
            raise ValueError("Geography batch denominator mismatch")
        audit_sha = digest(folder / "audit.json")
        for result in results:
            place = result["input"]
            key = place["place_id"]
            if (
                key not in expected
                or key in rows
                or place["name"] != expected[key]["name"]
            ):
                raise ValueError("Duplicate or changed Geography exact key")
            chosen = result["proposed"]
            selection = (
                {k: v for k, v in chosen.items() if k != "geometry"} if chosen else None
            )
            if selection and selection.get("receipt"):
                selection["receipt"] = str(Path(selection["receipt"]).resolve())
            rows[key] = dict(
                place_id=key,
                name=place["name"],
                status=(
                    "RESOLVED" if chosen else "UNRESOLVED_NO_ELIGIBLE_SOURCE_GEOMETRY"
                ),
                geometry=chosen["geometry"] if chosen else None,
                crs="EPSG:4326" if chosen else None,
                selection=selection,
                candidate_count=len(result["ranking"]),
                selection_rule="EXISTING_45_30_15_7_3_HIGHEST_AVAILABLE_NATIVE_GEOMETRY",
                evidence=dict(
                    path=str((folder / "audit.json").resolve()), sha256=audit_sha
                ),
                identities_added=0,
            )
    if set(rows) != set(expected):
        raise ValueError(f"Incomplete Geography batches: {len(rows)}/{len(expected)}")
    for failed in read_json(base / "geography_inputs/failed_inputs.json"):
        if failed["place_id"] in rows:
            raise ValueError("Duplicate failed Geography input")
        rows[failed["place_id"]] = dict(
            failed, geometry=None, crs=None, identities_added=0
        )
    if len(rows) != report["all_loc_targets"]:
        raise ValueError("Full LOC denominator mismatch")
    write_array(output, (rows[k] for k in sorted(rows)))
    bundle_geography_evidence(base, output.with_name(output.name + ".evidence.json.gz"))
    return dict(
        processed=len(rows),
        resolved=sum(r["status"] == "RESOLVED" for r in rows.values()),
        statuses=dict(Counter(r["status"] for r in rows.values())),
        sha256=digest(output),
    )


def populate_geography(
    model: Path,
    core_graph: Path,
    geography: Path,
    output_model: Path,
    output_graph: Path,
) -> dict:
    """Write a new model/graph; keep IDs, pair rows and native shapes unchanged."""
    from shapely.geometry import shape

    from Agent.geo_agent.compact_format import records, write_graph

    if output_model.exists() or output_graph.exists():
        raise FileExistsError("Preserve prior Geography outputs")
    manifest = read_json(model / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(model / name) != sha:
            raise ValueError("Core model input changed")
    places = {
        r["entity_id"]
        for r in read_json(model / "entities.json.gz")
        if r["type"] == "LOC"
    }
    rows = read_json(geography)
    by_id = {r["place_id"]: r for r in rows}
    if set(by_id) != places or len(rows) != len(places):
        raise ValueError("Geography must account for every exact LOC key once")
    resolved = 0
    for row in rows:
        if not row.get("status") or "PENDING" in row["status"]:
            raise ValueError("Geography still has pending targets")
        geometry = row.get("geometry")
        if geometry is not None:
            if row.get("crs") != "EPSG:4326":
                raise ValueError("Unsupported Geography CRS")
            geo = shape(geometry)
            if (
                geo.is_empty
                or not geo.is_valid
                or not (
                    -180 <= geo.bounds[0] <= geo.bounds[2] <= 180
                    and -90 <= geo.bounds[1] <= geo.bounds[3] <= 90
                )
            ):
                raise ValueError("Invalid Earth geometry")
            if row["status"] != "RESOLVED":
                raise ValueError("Geometry/status mismatch")
            resolved += 1
        elif row["status"] == "RESOLVED":
            raise ValueError("Resolved location lacks source geometry")
    reserve = 2 * (core_graph.stat().st_size + geography.stat().st_size) + 15 * 1024**3
    if shutil.disk_usage(output_model.parent).free < reserve:
        raise OSError("Insufficient enriched graph storage reserve")
    core_sha = digest(core_graph)
    reader = records(core_graph)
    _, metadata = next(reader)
    if metadata["model_manifest_sha256"] != digest(model / "manifest.json"):
        reader.close()
        raise ValueError("Core graph/model mismatch")
    nodes = [next(reader)[1] for _ in range(metadata["node_count"])]
    if {n["id"] for n in nodes if n["type"] == "location"} != places:
        reader.close()
        raise ValueError("Agent LOC population differs from model")
    for node in nodes:
        if node["id"] in by_id:
            row = by_id[node["id"]]
            node["geometry"] = row.get("geometry")
            node.setdefault("attributes", {}).update(
                geography_status=row["status"],
                geography_provenance={k: v for k, v in row.items() if k != "geometry"},
            )
    output_model.mkdir()
    for name in manifest["outputs"]:
        if name != "geography.json.gz":
            os.link(model / name, output_model / name)
    os.link(geography, output_model / "geography.json.gz")
    bundle = geography.with_name(geography.name + ".evidence.json.gz")
    if bundle.is_file():
        os.link(bundle, output_model / "geography_evidence.json.gz")
    status = "COMPLETE" if resolved == len(rows) else "COMPLETE_WITH_UNRESOLVED"
    report = dict(
        manifest,
        stage="MODEL_WITH_GEOGRAPHY",
        geography_status=status,
        geography_processed=len(rows),
        geography_resolved=resolved,
        geography_status_counts=dict(Counter(r["status"] for r in rows)),
        core_graph_sha256=core_sha,
        source_model_manifest_sha256=digest(model / "manifest.json"),
        outputs={p.name: digest(p) for p in output_model.iterdir() if p.is_file()},
    )
    write_object(output_model / "manifest.json", report)
    output_graph.mkdir()
    metadata = dict(
        metadata,
        geography_status=status,
        geometry_crs="EPSG:4326",
        geography_sha256=digest(geography),
        model_manifest_sha256=digest(output_model / "manifest.json"),
        core_graph_sha256=core_sha,
    )
    try:
        write_graph(
            output_graph / "agent_graph.json.gz",
            metadata,
            nodes,
            (r for k, r in reader if k == "pair"),
        )
    finally:
        reader.close()
    os.link(core_graph.parent / "relations.json.gz", output_graph / "relations.json.gz")
    schema = core_graph.parent / "relations_schema.json"
    if schema.exists():
        os.link(schema, output_graph / schema.name)
    if digest(core_graph) != core_sha:
        raise ValueError("Core graph changed during enrichment")
    write_object(
        output_graph / "manifest.json",
        dict(
            metadata,
            stage="ENRICHED_GRAPH_EXPORTED",
            outputs={p.name: digest(p) for p in output_graph.iterdir() if p.is_file()},
        ),
    )
    return report


@contextmanager
def slow_nominatim(client, state: Path, *, now=None, sleep=None):
    """One owner, one machine; persist the long-run four-per-minute bound."""
    from .rebuild_poc import write

    now, sleep = now or time.time, sleep or time.sleep
    original = client.request_json

    def paced(url, **kwargs):
        if any(
            url.startswith(endpoint + "/") for endpoint in client.NOMINATIM.values()
        ):
            prior = read_json(state) if state.exists() else {"network_requests": 0}
            delay = max(0.0, prior.get("last_started_epoch", 0) + 15.1 - now())
            if delay:
                sleep(delay)
            write(
                state,
                dict(
                    last_started_epoch=now(),
                    network_requests=prior["network_requests"] + 1,
                    minimum_interval_seconds=15.1,
                    policy="https://operations.osmfoundation.org/policies/nominatim/",
                ),
            )
        return original(url, **kwargs)

    client.request_json = paced
    try:
        yield
    finally:
        client.request_json = original


def prepare_batch(base: Path, start: int, size: int = 250) -> Path:
    """Run the existing source-query preparation on an exact, disjoint slice."""
    from . import geography_comparison
    from .rebuild_poc import write

    targets = read_json(base / "geography_inputs/targets.json")
    if (
        type(start) is not int
        or type(size) is not int
        or not 0 <= start < len(targets)
        or size <= 0
    ):
        raise ValueError("Invalid Geography batch range")
    folder = base / "batches" / f"{start:06d}"
    folder.mkdir(parents=True)
    sample = folder / "sample.json"
    write_object(sample, targets[start : start + size])
    comparison = folder / "retrieval"
    geography_comparison.prepare(
        base, comparison, sample, all_targets=True, model_dir=base / "model"
    )
    # Full original-page LOC names are supplied by preparation, without an O(N^2)
    # scan of other targets or a global name-to-identity join.
    mentions = {
        m["mention_id"]: m for m in read_json(base / "mentions_pages/mentions.json.gz")
    }
    evidence = read_json(comparison / "evidence.json")
    for row in evidence.values():
        row["same_page_location_names"] = mentions[row["mention_id"]][
            "same_page_location_names"
        ]
    write(comparison / "evidence.json", evidence, compact=True)
    plan = read_json(comparison / "plan.json")
    plan["outputs"]["evidence.json"] = digest(comparison / "evidence.json")
    write(comparison / "plan.json", plan, compact=True)
    write_object(
        folder / "manifest.json",
        dict(
            start=start,
            size=len(targets[start : start + size]),
            total_ready_targets=len(targets),
            sample_sha256=digest(sample),
            comparison_plan_sha256=digest(comparison / "plan.json"),
            source_report_sha256=digest(base / "geography_inputs/report.json"),
        ),
    )
    return folder


def candidate_records(comparison: Path, metadata: Path, client) -> dict:
    """Reuse the established >=80% candidate link rule, never assign identities."""
    from .geography_ranking_sample import similarity

    if read_json(comparison / "progress.json")["status"] != "RETRIEVED":
        raise ValueError("Complete retrieval before candidate-coordinate evidence")
    if (comparison / "candidate_records.json.gz").exists():
        raise FileExistsError("Completed candidate records")
    sample = read_json(comparison / "sample.json")
    arms = [
        read_json(comparison / f"sources/whg_{a}.json")["response"]
        for a in ("native", "existing_dated")
    ]
    wanted = sorted(
        {
            candidate["id"].split(":")[-1]
            for place in sample
            for arm in arms
            for candidate in arm.get(place["place_id"], {}).get("result", [])
            if candidate["id"].startswith("place:wd:")
            and max(
                (
                    similarity(place["name"], n)
                    for n in [candidate["name"], *candidate.get("alt_names", [])]
                ),
                default=0,
            )
            >= 0.8
        }
    )
    metadata_sha = digest(metadata)
    saved = read_json(metadata)
    records = {
        q: dict(requested_qid=q, entity=saved[q])
        for q in wanted
        if q in saved and "claims" in saved[q] and "missing" not in saved[q]
    }
    evidence = {
        q: dict(path=str(metadata.resolve()), sha256=metadata_sha) for q in records
    }
    unavailable = []
    missing = [q for q in wanted if q not in records]
    for start in range(0, len(missing), 50):
        batch = missing[start : start + 50]
        data, receipt, stamp = client.query(
            "https://www.wikidata.org/w/api.php",
            dict(
                action="wbgetentities",
                ids="|".join(batch),
                props="labels|claims|info",
                languages="en",
            ),
        )
        for q in batch:
            native = data.get("entities", {}).get(q)
            if native is None:
                raise ValueError(f"Candidate native record absent: {q}")
            evidence[q] = dict(file=receipt, retrieved_utc=stamp)
            if "missing" in native:
                unavailable.append(q)
            else:
                records[q] = dict(requested_qid=q, entity=native)
    if digest(metadata) != metadata_sha:
        raise ValueError("Candidate metadata changed during retrieval")
    with gzip.open(
        comparison / "candidate_records.json.gz", "xt", encoding="utf-8"
    ) as stream:
        json.dump(records, stream, ensure_ascii=False, allow_nan=False)
    result = dict(
        status="CANDIDATE_GEOMETRY_EVIDENCE_ONLY",
        candidate_qids=len(wanted),
        available_records=len(records),
        missing_coordinate_records=unavailable,
        identities_added=0,
        provenance=evidence,
        outputs={
            "candidate_records.json.gz": digest(
                comparison / "candidate_records.json.gz"
            )
        },
    )
    write_object(comparison / "candidate_records_report.json", result)
    return result


def prepare_geography(model: Path, core_release: Path, output: Path) -> dict:
    """Gate source work on the released core; never assign Wikidata identities."""
    if output.exists():
        raise FileExistsError(output)
    release = read_json(core_release / "manifest.json")
    if release.get("stage") != "CORE_RELEASE_GEOGRAPHY_PENDING" or release.get(
        "outputs", {}
    ).get("model/manifest.json") != digest(model / "manifest.json"):
        raise ValueError("A verified matching core release is required first")
    for name, sha in release["outputs"].items():
        if digest(core_release / name) != sha:
            raise ValueError(f"Changed core release artifact: {name}")
    manifest = read_json(model / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(model / name) != sha:
            raise ValueError(f"Changed model input: {name}")
    source = Path(manifest["input"]["path"])
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Pinned Daniel input changed")
    places = {
        p["entity_id"]: p
        for p in read_json(model / "entities.json.gz")
        if p["type"] == "LOC"
    }
    pages = {p["source_key"]: p for p in read_json(model / "wiki_pages.json.gz")}
    first = {}
    page_names = {}
    # Count every raw row, including DATE, to preserve original mention indexes.
    for index, row in enumerate(
        r
        for b in pq.ParquetFile(source).iter_batches(batch_size=8192)
        for r in b.to_pylist()
    ):
        if row["entity_group"] != "LOC":
            continue
        key = entity_id(row["word"], "LOC")
        if key not in places:
            raise ValueError("LOC exact key missing from model")
        page = pages[row["Source"]]
        page_index = page.get("canonical_page_index", page["page_index"])
        page_names.setdefault(page_index, set()).add(row["word"])
        if key in first:
            continue
        start, end = row["start"], row["end"]
        if not (
            type(start) is int
            and type(end) is int
            and 0 <= start <= end <= len(row["Text"])
            and row["Text"][start:end] == row["word"]
        ):
            continue
        first[key] = dict(
            row,
            mention_id=f"mention:{index}",
            entity_id=key,
            original_source_key=row["Source"],
            Source=page.get("title", row["Source"]),
            wiki_site="enwiki",
            wiki_page_id=page["wiki_page_id"],
            page_index=page_index,
        )
    for mention in first.values():
        mention["same_page_location_names"] = sorted(page_names[mention["page_index"]])
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Input changed during Geography preparation")
    output.mkdir(parents=True)
    for name in ["model", "entities", "mentions_pages", "geography_inputs"]:
        (output / name).mkdir()
    for name in [*manifest["outputs"], "manifest.json"]:
        os.link(model / name, output / "model" / name)
    # There is no accepted native identity for any name/type entity.
    write_array(output / "mentions_pages/mentions.json.gz", first.values())
    with gzip.open(
        output / "entities/full_records.json.gz", "xt", encoding="utf-8"
    ) as stream:
        stream.write("{}")
    targets = []
    for key, place in sorted(places.items()):
        if key not in first:
            continue
        targets.append(
            dict(
                place_id=key,
                name=place["name"],
                type="LOC",
                aliases=[],
                wikidata_id=None,
                identity_status="EXACT_NAME_TYPE_KEY_ONLY",
                lookup_method="NAME_CONTEXT_GEOMETRY_ONLY",
                source_context=[first[key]],
                date_basis="EXISTING_DEFAULT_NO_FACTUAL_LOC_EVENT_DATE",
                **selection_value([], key),
            )
        )
    failed = [
        dict(place_id=k, name=v["name"], status="FAILED_INPUT_NO_VALID_MENTION_SPAN")
        for k, v in sorted(places.items())
        if k not in first
    ]
    write_object(output / "geography_inputs/targets.json", targets)
    write_object(output / "geography_inputs/failed_inputs.json", failed)
    result = dict(
        status="GEOGRAPHY_INPUTS_READY",
        all_loc_targets=len(places),
        ready_targets=len(targets),
        failed_input_targets=len(failed),
        new_source_requests=0,
        identity_assignments_changed=False,
        input_sha256=manifest["input"]["sha256"],
        core_release_manifest_sha256=digest(core_release / "manifest.json"),
        source_manifest_sha256=digest(model / "manifest.json"),
        outputs={
            p.relative_to(output).as_posix(): digest(p)
            for p in output.rglob("*")
            if p.is_file()
        },
    )
    write_object(output / "geography_inputs/report.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--model", type=Path, required=True)
    prepare.add_argument("--core-release", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--base", type=Path, required=True)
    run.add_argument("--metadata", type=Path, required=True)
    run.add_argument("--batch-size", type=int, default=250)
    run.add_argument("--source-project", type=Path, required=True)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--base", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)
    enrich = commands.add_parser("enrich")
    for name in ["model", "core-graph", "geography", "output-model", "output-graph"]:
        enrich.add_argument("--" + name, type=Path, required=True)
    complete = commands.add_parser("complete")
    for name in [
        "model",
        "core-graph",
        "core-release",
        "prepared",
        "output",
        "metadata",
        "agent-python",
        "source-project",
    ]:
        complete.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.command == "prepare":
        result = prepare_geography(args.model, args.core_release, args.output)
    elif args.command == "run":
        if not (args.base / "source_cache_manifest.json").exists():
            configure_sources(args.base, args.source_project)
        else:
            import importlib

            from .geography_sample import tools

            tools()
            importlib.import_module("GEO_OBJECT_EXTRACTION_POC").ENV_FILE = (
                args.source_project / ".env"
            )
        result = run_population(args.base, args.metadata, batch_size=args.batch_size)
    elif args.command == "aggregate":
        result = aggregate_geography(args.base, args.output)
    elif args.command == "enrich":
        result = populate_geography(
            args.model,
            args.core_graph,
            args.geography,
            args.output_model,
            args.output_graph,
        )
    else:
        result = complete_geography(
            args.model,
            args.core_graph,
            args.core_release,
            args.prepared,
            args.output,
            args.metadata,
            args.agent_python,
            args.source_project,
        )
    LOG.info("Geography %s", {k: v for k, v in result.items() if k != "outputs"})

"""Freeze nested page sets or build core tables from verified saved decisions.

Larger deliveries still require preceding acceptance and Geography decisions.
The core build does not run a model or populate Events, Relations or Geography.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import runpy
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType

from GG_Data.entity_resolution.luke_pilot.data import sha256
from GG_Data.pipeline.poc import read_json


def archived_readiness(gate: Path, model: Path) -> dict:
    """Load a verified historical gate without restoring removed live modules.

    Only the caller's hash-checked archived model supplies the old import. The
    temporary alias is removed after loading; no old receipt or code is edited.
    """
    old_name = "GG_Data.entity_resolution.hundred_page_pilot.model"
    previous = sys.modules.get(old_name)
    archived_model = ModuleType(old_name)
    archived_model.__dict__.update(runpy.run_path(str(model)))
    sys.modules[old_name] = archived_model
    try:
        return runpy.run_path(str(gate))
    finally:
        if previous is None:
            sys.modules.pop(old_name, None)
        else:
            sys.modules[old_name] = previous


def freeze_scopes(
    rows: list[dict], old_ten_titles: list[str], source_titles: list[str] | None = None
) -> dict:
    pages = {int(r["page_id"]) for r in rows}
    ten = set()
    for title in old_ten_titles:
        found = {
            int(r["page_id"])
            for r in rows
            if r.get("source_title", r["Source"]) == title
        }
        if len(found) > 1:
            raise ValueError(f"Prior title must identify one page: {title}")
        ten.update(found)
    if len(ten) < 3:
        raise ValueError(
            "Prior titles must identify at least three retained pages; each title maps to one page"
        )
    three = set(
        sorted(
            ten, key=lambda p: hashlib.sha256(f"20261029\0{p}".encode()).hexdigest()
        )[:3]
    )
    # OWNER approved filling missing old titles from the saved sample, in its
    # original order. No model outputs influence page membership.
    if len(ten) < 10:
        if source_titles is None:
            raise ValueError(
                "Missing prior pages require the approved saved-title order"
            )
        for title in source_titles:
            ten.update(
                int(r["page_id"])
                for r in rows
                if r.get("source_title", r["Source"]) == title
            )
            if len(ten) >= 10:
                break
    if len(ten) != 10:
        raise ValueError("Ten-page scope must contain exactly ten pages")
    return {
        label: {
            "page_ids": sorted(selected),
            "used_revisions": sorted(
                {
                    (int(r["page_id"]), int(r["revision_id"]))
                    for r in rows
                    if int(r["page_id"]) in selected
                }
            ),
            "original_rows": sum(int(r["page_id"]) in selected for r in rows),
        }
        for label, selected in (("3", three), ("10", ten), ("100", pages))
    }


def prepare(
    input_dir: Path,
    output: Path,
    *,
    matching_subdir: str = "matching_k80_v2",
    mentions_name: str = "selected_mentions.parquet",
) -> dict:
    import pyarrow.parquet as pq

    selection = json.loads((input_dir / "selection.json").read_text(encoding="utf-8"))
    rows = pq.read_table(input_dir / "selected_mentions.parquet").to_pylist()
    scopes = freeze_scopes(
        rows, selection["old_ten_titles"], selection["source_titles"]
    )
    if len(scopes["100"]["page_ids"]) != 100:
        raise ValueError("Saved pilot must contain 100 distinct pages")
    inputs = [
        "selection.json",
        "selected_mentions.parquet",
        "revisions.parquet",
        f"{matching_subdir}/groups.jsonl",
        f"{matching_subdir}/jobs.jsonl",
        f"{matching_subdir}/exact_pairs.parquet",
    ]
    if mentions_name not in inputs:
        inputs.append(mentions_name)
    manifest = dict(
        schema_version=1,
        original_input_sha256=selection["input_sha256"],
        selection_rule="Retained old pages first; fill ten in saved source_titles order. Three by ascending SHA256(20261029 NUL page_id) among retained pages. OWNER approved 2026-10-29.",
        scopes=scopes,
        inputs={name: sha256(input_dir / name) for name in inputs},
    )
    if (
        matching_subdir != "matching_k80_v2"
        or mentions_name != "selected_mentions.parquet"
    ):
        manifest.update(
            schema_version=2,
            matching_subdir=matching_subdir,
            mentions_name=mentions_name,
        )
    output.mkdir(parents=True, exist_ok=False)
    (output / "scope_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    # Subset immutable prepared questions; do not rerank or change candidate pools.
    source = input_dir / matching_subdir / "jobs.jsonl"
    for label, scope in scopes.items():
        selected = set(scope["page_ids"])
        with source.open(encoding="utf-8") as stream, (
            output / f"jobs_{label}.jsonl"
        ).open("x", encoding="utf-8") as target:
            for line in stream:
                if json.loads(line)["page_id"] in selected:
                    target.write(line)
    return manifest


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_stage(
    input_dir: Path,
    scope_dir: Path,
    output: Path,
    scope: str,
    stage: str,
    *,
    native_dir: Path | None = None,
    scoped_inventory_path: Path | None = None,
) -> dict:
    """Save pending or exact tables together, before model decisions exist.

    Read the same frozen inputs as the final build. No provisional identities
    are created here. Accepted exact identities use full native records.
    """
    import pyarrow.parquet as pq

    from GG_Data.pipeline.post_qid_eda import summarize
    from GG_Data.pipeline.post_qid_entities import populate as entities_populate
    from GG_Data.pipeline.post_qid_mentions import populate as mentions_populate
    from GG_Data.pipeline.post_qid_pages import run as pages_run

    if stage not in {"pending", "exact"}:
        raise ValueError("Early snapshot must be pending or exact")
    manifest_path = scope_dir / "scope_manifest.json"
    manifest = read_json(manifest_path)
    bindings = {str(manifest_path.resolve()): sha256(manifest_path)}
    scoped_inventory = None
    if scoped_inventory_path is not None:
        bindings[str(scoped_inventory_path.resolve())] = sha256(scoped_inventory_path)
        scoped_inventory = pq.read_table(scoped_inventory_path).to_pylist()
    for name, expected in manifest["inputs"].items():
        path = input_dir / name
        if sha256(path) != expected:
            raise ValueError(f"Frozen stage input differs: {path}")
        bindings[str(path.resolve())] = expected
    selected = manifest["scopes"][scope]
    pages = set(selected["page_ids"])
    rows = [
        r
        for r in pq.read_table(
            input_dir / manifest.get("mentions_name", "selected_mentions.parquet")
        ).to_pylist()
        if r["page_id"] in pages
    ]
    if len(rows) != selected["original_rows"]:
        raise ValueError("Early snapshot original row coverage differs")
    matching = input_dir / manifest.get("matching_subdir", "matching_k80_v2")
    groups = [g for g in _jsonl(matching / "groups.jsonl") if g["page_id"] in pages]
    gids = {g["id"] for g in groups}
    pairs = (
        [
            p
            for p in pq.read_table(matching / "exact_pairs.parquet").to_pylist()
            if p["group_id"] in gids
        ]
        if stage == "exact"
        else []
    )
    records, sources = {}, {}
    if pairs:
        if native_dir is None:
            raise ValueError("Exact snapshot needs full native records")
        for name in ("full_records.json.gz", "sources.json"):
            bindings[str((native_dir / name).resolve())] = sha256(native_dir / name)
        records, sources = read_json(native_dir / "full_records.json.gz"), read_json(
            native_dir / "sources.json"
        )
        if not {p["qid"] for p in pairs} <= records.keys() & sources.keys():
            raise ValueError("Exact snapshot native acquisition is incomplete")
    digest = manifest["original_input_sha256"]
    tables = mentions_populate(
        rows,
        groups,
        pairs,
        input_sha256=digest,
        dataset_namespace=digest,
        stage=stage,
        scoped_inventory=scoped_inventory,
    )
    tables["entities"] = entities_populate(
        groups,
        pairs,
        input_sha256=digest,
        dataset_namespace=digest,
        stage=stage,
        eligible_group_ids=gids,
        native_records=records,
        provenance=sources,
        scoped_inventory=scoped_inventory,
    )
    with tempfile.TemporaryDirectory(prefix="geoai-stage-pages-") as directory:
        pages_run(input_dir, Path(directory) / "pages", pages)
        tables["wiki_pages"] = read_json(Path(directory) / "pages/wiki_pages.json.gz")
    _set_importance(tables)
    summarize(tables)
    return _save_tables(
        output,
        tables,
        dict(
            status="MATCHING_IN_PROGRESS",
            scope=scope,
            processing_stage=stage,
            page_ids=sorted(pages),
            run_id=sha256(manifest_path),
            inputs=bindings,
            pending=["model", "finalization", "Events", "Relations", "Geography"],
            **_scoped_manifest(scoped_inventory_path, tables),
        ),
    )


def _save_tables(output: Path, tables: dict, result: dict) -> dict:
    """Publish one complete local snapshot; never overwrite an earlier stage."""
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=output.name + "-staging-", dir=output.parent
    ) as directory:
        stage_dir = Path(directory) / "complete"
        stage_dir.mkdir()
        for name, data in tables.items():
            with gzip.open(
                stage_dir / f"{name}.json.gz", "wt", encoding="utf-8"
            ) as stream:
                json.dump(data, stream, ensure_ascii=False)
        result.update(
            counts={n: len(t) for n, t in tables.items()},
            outputs={p.name: sha256(p) for p in stage_dir.glob("*.json.gz")},
        )
        (stage_dir / "manifest.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        stage_dir.rename(output)
    return result


def _scoped_manifest(path: Path | None, tables: dict) -> dict:
    if path is None:
        return {}
    from GG_Data.entity_resolution.hundred_page_pilot.filter_qid_inventory import (
        POLICY_VERSION,
    )

    return dict(
        scoped_qid_inventory=dict(
            path=str(path.resolve()), sha256=sha256(path), policy_version=POLICY_VERSION
        ),
        used_revisions=sorted(
            [p["wiki_page_id"], p["revision_id"]] for p in tables["wiki_pages"]
        ),
    )


def _set_importance(tables: dict) -> None:
    """Use the same occurrence/page counts in early and final core snapshots."""
    occurrences, pages = defaultdict(set), defaultdict(set)
    mentions = {m["mention_id"]: m for m in tables["mentions"]}
    for link in tables["mention_entity_links"]:
        identity, mid = link["entity_id"], link["mention_id"]
        occurrences[identity].add(mid)
        mention = mentions[mid]
        pages[identity].add((mention["wiki_site"], mention["wiki_page_id"]))
    for entity in tables["entities"]:
        identity = entity["entity_id"]
        count, source_count = len(occurrences[identity]), len(pages[identity])
        entity.update(
            importance=count * source_count,
            unique_original_mention_count=count,
            distinct_source_page_count=source_count,
        )
        entity["attributes"]["importance_basis"] = dict(
            total_mentions=count,
            distinct_source_pages=source_count,
            formula="unique original mention IDs per identity * distinct original source pages",
            status="LEGACY_COUNT_PRODUCT_WITH_TYPED_QID_DEDUPLICATION",
        )
        entity["attributes"]["normalized_mention_frequency"] = count / len(mentions)
        entity["attributes"]["normalized_mention_frequency_denominator"] = len(mentions)


def assemble(core_dir: Path, event_dir: Path, output: Path) -> dict:
    """Join checked core and article-bound enrichment into one local version."""
    from GG_Data.pipeline.post_qid_eda import CORE_TABLES, summarize
    from GG_Data.pipeline.post_qid_native import _stage

    core = read_json(core_dir / "manifest.json")
    if core.get("processing_stage") not in {None, "legacy", "final"}:
        raise ValueError("Core matching must be final before assembly")
    for name, expected in core["outputs"].items():
        if sha256(core_dir / name) != expected:
            raise ValueError("Core snapshot changed before assembly")
    receipt = _stage(event_dir)
    if receipt.get("status") != "NATIVE_EVENT_RELATIONS_READY" or receipt.get(
        "scope"
    ) != core.get("scope"):
        raise ValueError("Event enrichment is incomplete or has a different scope")
    if receipt.get("phase") not in {
        "ARTICLE_EVENT_BOUNDARY",
        "CACHED_ARTICLE_EVENT_RELATIONS",
    }:
        raise ValueError("Final assembly requires article-bound Event enrichment")
    core_manifest = core_dir / "manifest.json"
    if receipt.get("inputs", {}).get(str(core_manifest.resolve())) != sha256(
        core_manifest
    ):
        raise ValueError("Event enrichment must bind this exact core manifest")
    for name, expected in receipt.get("inputs", {}).items():
        if sha256(Path(name)) != expected:
            raise ValueError("Enrichment input changed before assembly")
    tables = {name: read_json(core_dir / f"{name}.json.gz") for name in CORE_TABLES}
    event_entities = read_json(event_dir / "event_entities.json.gz")
    event_rows = read_json(event_dir / "events.json.gz")
    if "scoped_qid_inventory" in core:
        _validate_scoped_events(core, receipt, tables, event_entities, event_rows)
    tables["entities"] += event_entities
    tables.update(
        {
            name: read_json(event_dir / f"{name}.json.gz")
            for name in ("events", "relations")
        }
    )
    result = {
        **core,
        "status": "ARTICLE_TABLES_COMPLETE_GEOGRAPHY_DEFERRED",
        "pending": ["Geography"],
        "counts": {n: len(v) for n, v in tables.items()},
        "inputs": {
            **core.get("inputs", {}),
            str((core_dir / "manifest.json").resolve()): sha256(
                core_dir / "manifest.json"
            ),
            str((event_dir / "receipt.json").resolve()): sha256(
                event_dir / "receipt.json"
            ),
        },
    }
    summarize(tables, result)
    return _save_tables(output, tables, result)


def _validate_scoped_events(
    core: dict, receipt: dict, tables: dict, event_entities: list, events: list
) -> None:
    """Keep final Event identities inside the exact retained article inventory."""
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.filter_qid_inventory import (
        POLICY_VERSION,
        source_allowed,
    )

    inventory = core["scoped_qid_inventory"]
    if (
        not isinstance(inventory, dict)
        or not isinstance(inventory.get("path"), str)
        or not Path(inventory["path"]).is_absolute()
        or inventory.get("policy_version") != POLICY_VERSION
    ):
        raise ValueError("Invalid scoped QID inventory binding")
    path = Path(inventory["path"])
    if sha256(path) != inventory.get("sha256") or receipt.get("inputs", {}).get(
        str(path.resolve())
    ) != inventory.get("sha256"):
        raise ValueError("Event receipt must bind the unchanged scoped QID inventory")
    revisions = sorted(
        [p["wiki_page_id"], p["revision_id"]] for p in tables["wiki_pages"]
    )
    if (
        core.get("used_revisions") != revisions
        or receipt.get("used_revisions") != revisions
    ):
        raise ValueError("Event receipt must use the exact core used revisions")
    revision_keys = {tuple(pair) for pair in revisions}
    allowed, seen = set(), set()
    for row in pq.read_table(path).to_pylist():
        if (
            row.get("qid_filter_policy_version") != POLICY_VERSION
            or row.get("qid_source_status")
            not in {"KEEP", "REVIEW_KEEP", "UNKNOWN_KEEP"}
            or not source_allowed(row)
            or not isinstance(row.get("type_categories"), list)
            or not all(isinstance(t, str) for t in row["type_categories"])
            or type(row.get("type_unknown")) is not bool
            or type(row.get("page_id")) is not int
            or type(row.get("revision_id")) is not int
            or not isinstance(row.get("qid"), str)
            or not re.fullmatch(r"Q[1-9]\d*", row["qid"])
        ):
            raise ValueError("Event inventory must contain retained enriched QIDs")
        key = row["page_id"], row["revision_id"], row["qid"]
        if key in seen:
            raise ValueError("Duplicate scoped QID inventory row")
        seen.add(key)
        if key[:2] in revision_keys:
            allowed.add(row["qid"])
    added = {r["entity_id"] for r in event_entities} | {r["event_id"] for r in events}
    if not added <= allowed:
        raise ValueError("Event QID is outside the retained inventory used revisions")


def validate_approval_input(manifest_path: Path, scope_path: Path) -> None:
    """A portable approval must identify this input version and frozen scope."""
    approved, frozen = read_json(manifest_path), read_json(scope_path)
    expected = {
        "scope_manifest_sha256": sha256(scope_path),
        "original_input_sha256": frozen["original_input_sha256"],
        "original_mentions_sha256": frozen["inputs"]["selected_mentions.parquet"],
    }
    if any(approved.get(key) != value for key, value in expected.items()):
        raise ValueError("Experimental approval input or frozen scope differs")


def build_core(
    input_dir: Path,
    scope_dir: Path,
    inference_dir: Path,
    native_dir: Path,
    output: Path,
    scope: str = "3",
    *,
    model_dir: Path | None = None,
    training_dir: Path | None = None,
    readiness_dir: Path | None = None,
    experimental_approval_path: Path | None = None,
    approval_manifest_path: Path | None = None,
    stage: str = "legacy",
    scoped_inventory_path: Path | None = None,
) -> dict:
    """Verify archived decisions, then write the four core tables; no inference."""
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.readiness import REQUIRED_FILES
    from GG_Data.entity_resolution.hundred_page_pilot.resolve_entities import (
        select_loop,
    )
    from GG_Data.pipeline.post_qid_entities import populate as entities_populate
    from GG_Data.pipeline.post_qid_mentions import populate as mentions_populate
    from GG_Data.pipeline.post_qid_pages import run as pages_run

    model_dir = model_dir or input_dir / "train_20261029"
    training_dir = training_dir or input_dir / "training_k80_v2"
    readiness_dir = readiness_dir or model_dir
    bindings = {}

    def bind(path: Path, expected: str | None = None) -> str:
        if not path.is_file():
            raise ValueError(f"Missing archived input: {path}")
        actual = sha256(path)
        if expected is not None and actual != expected:
            raise ValueError(f"Archived hash differs: {path}")
        bindings[str(path.resolve())] = actual
        return actual

    scoped_inventory = None
    if scoped_inventory_path is not None:
        bind(scoped_inventory_path)
        scoped_inventory = pq.read_table(scoped_inventory_path).to_pylist()
    bind(scope_dir / "scope_manifest.json")
    manifest = read_json(scope_dir / "scope_manifest.json")
    matching = manifest.get("matching_subdir", "matching_k80_v2")
    mentions_name = manifest.get("mentions_name", "selected_mentions.parquet")
    required_inputs = {
        "selection.json",
        mentions_name,
        "revisions.parquet",
        f"{matching}/groups.jsonl",
        f"{matching}/jobs.jsonl",
        f"{matching}/exact_pairs.parquet",
    }
    if not required_inputs <= manifest.get("inputs", {}).keys():
        raise ValueError("Missing frozen scope input bindings")
    for name, expected in manifest["inputs"].items():
        bind(input_dir / name, expected)
    if (
        read_json(input_dir / "selection.json").get("input_sha256")
        != manifest["original_input_sha256"]
    ):
        raise ValueError("Original input identity differs from frozen selection")
    selected = manifest["scopes"][scope]
    pages = set(selected["page_ids"])
    jobs_path = scope_dir / f"jobs_{scope}.jsonl"
    run_id = bind(inference_dir / "inference_inputs.json")
    signature = read_json(inference_dir / "inference_inputs.json")
    bind(jobs_path, signature["jobs_sha256"])
    bind(model_dir / "full_best.pt", signature["checkpoint_sha256"])
    bind(readiness_dir / "readiness.json", signature["readiness_sha256"])
    readiness = read_json(readiness_dir / "readiness.json")
    if (
        readiness.get("technical_status") != "PASS"
        or readiness.get("checkpoint_sha256") != signature["checkpoint_sha256"]
    ):
        raise ValueError("Archived technical readiness failed or checkpoint differs")
    # Preserve remote readiness bytes. Verify the executed code through the local
    # archived copies rather than rewriting remote absolute paths in the receipt.
    if not REQUIRED_FILES <= readiness.get("files", {}).keys():
        raise ValueError("Missing required archived readiness evidence roles")
    code_names = {
        "training_code": "train.py",
        "inference_code": "match.py",
        "model_code": "model.py",
        "readiness_code": "readiness.py",
    }
    # Old runs used match.py; newly separated runs archive resolve_entities.py.
    inference_name = Path(readiness["files"]["inference_code"]["path"]).name
    if inference_name not in {"match.py", "resolve_entities.py"}:
        raise ValueError("Unknown archived inference entry")
    code_names["inference_code"] = inference_name
    local_paths = {}
    for role, name in code_names.items():
        binding = readiness.get("files", {}).get(role)
        if binding is None:
            raise ValueError(f"Missing executed-code binding: {role}")
        bind(scope_dir / "code_archive" / name, binding["sha256"])
        local_paths[role] = scope_dir / "code_archive" / name
    for role, binding in readiness["files"].items():
        if role in code_names:
            continue
        if role.startswith("input:"):
            local = training_dir / role.removeprefix("input:")
        elif role == "public_manifest":
            local = training_dir / "public_manifest.json"
        elif role in {"checkpoint_inspection", "restore_check"}:
            local = readiness_dir / Path(binding["path"]).name
        else:
            local = model_dir / Path(binding["path"]).name
        bind(local, binding["sha256"])
        if not role.startswith("input:"):
            local_paths[role] = local
    # Run only the hash-verified, archived gate used by this inference. Its
    # build step inspects metadata and hashes; it neither restores nor scores.
    archived_gate = archived_readiness(
        local_paths["readiness_code"], local_paths["model_code"]
    )
    observed = archived_gate["build_readiness"](
        model_dir / "full_best.pt", local_paths, training_dir
    )

    def portable(record: dict) -> dict:
        return {
            **{
                k: v for k, v in record.items() if k not in {"files", "input_directory"}
            },
            "files": {role: b["sha256"] for role, b in record["files"].items()},
        }

    if (
        portable(observed) != portable(readiness)
        or observed["technical_status"] != "PASS"
    ):
        raise ValueError(
            "Local archived readiness validation differs from saved evidence"
        )
    if "experimental_approval_sha256" in signature:
        approval_path = (
            experimental_approval_path
            or model_dir / "experimental_three_page_approval.json"
        )
        bind(approval_path, signature["experimental_approval_sha256"])
        approval = read_json(approval_path)
        if stage != "legacy":
            from GG_Data.entity_resolution.hundred_page_pilot.readiness import (
                validate_experimental_scope,
            )

            validate_experimental_scope(
                approval,
                model_dir / "full_best.pt",
                jobs_path,
                manifest_path=approval_manifest_path,
            )
            validate_approval_input(
                approval_manifest_path or Path(approval["manifest"]["path"]),
                scope_dir / "scope_manifest.json",
            )
        elif not (
            scope == "3"
            and len(pages) == 3
            and approval.get("approved_by") == "OWNER"
            and approval.get("scope") == "experimental_three_pages"
            and approval.get("decision")
            == "Allow the experimental three-page run with this model"
            and approval.get("checkpoint_sha256") == signature["checkpoint_sha256"]
            and approval.get("jobs_sha256") == signature["jobs_sha256"]
            and set(approval.get("page_ids", [])) == pages
        ):
            raise ValueError(
                "Experimental approval does not cover this immutable scope"
            )
    elif readiness.get("quality_status") != "PASS_PUBLIC_TARGETS":
        raise ValueError("Failed quality has no archived OWNER disposition")
    jobs = _jsonl(jobs_path)
    all_jobs = _jsonl(input_dir / matching / "jobs.jsonl")
    if jobs != [job for job in all_jobs if job["page_id"] in pages]:
        raise ValueError("Slice jobs differ from frozen candidate questions")
    jobs_by_id = {j["id"]: j for j in jobs}
    if len(jobs_by_id) != len(jobs):
        raise ValueError("Duplicate inference job")
    for name in (
        "scores.jsonl",
        "decisions.jsonl",
        "model_pairs.jsonl",
        "inference_summary.json",
    ):
        bind(inference_dir / name)
    summary = read_json(inference_dir / "inference_summary.json")
    if summary.get("questions") != len(jobs) or any(
        summary.get(k) != v for k, v in signature.items()
    ):
        raise ValueError("Inference summary differs from immutable signature")
    scores = _jsonl(inference_dir / "scores.jsonl")
    by_score = {r["id"]: r for r in scores}
    if len(by_score) != len(scores) or by_score.keys() != jobs_by_id.keys():
        raise ValueError("Every frozen job must have exactly one completed score row")
    expected_pairs, expected_decisions = [], []
    for job in jobs:
        options = by_score[job["id"]]["options"]
        values = {v["id"]: v["score"] for v in options}
        candidates = {c["id"]: c for c in job["candidates"]}
        if (
            len(values) != len(options)
            or len(candidates) != len(job["candidates"])
            or values.keys() != candidates.keys() | {None}
        ):
            raise ValueError("Option scores differ from exact frozen candidate pool")
        chosen, trace = select_loop(
            {k: v for k, v in values.items() if k is not None}, values[None]
        )
        key = {k: job[k] for k in ("id", "page_id", "revision_id", "qid")}
        expected_pairs.extend(
            {
                **key,
                "group_id": g,
                "entity_group": candidates[g].get("type"),
                "method": "model",
            }
            for g in chosen
        )
        expected_decisions.extend(
            {**key, **step, "excluded_count": job["excluded_count"]} for step in trace
        )
    pairs = _jsonl(inference_dir / "model_pairs.jsonl")
    decisions = _jsonl(inference_dir / "decisions.jsonl")
    if pairs != expected_pairs or decisions != expected_decisions:
        raise ValueError(
            "Model pairs or decision trace differ from completed frozen scores"
        )
    by_decision = {
        (d["id"], d["group_id"]): d for d in decisions if d["decision"] == "select"
    }
    for pair in pairs:
        decision = by_decision[pair["id"], pair["group_id"]]
        pair.update(
            run_id=run_id,
            checkpoint_sha256=signature["checkpoint_sha256"],
            readiness_sha256=signature["readiness_sha256"],
            decision_reference=dict(
                path=str((inference_dir / "decisions.jsonl").resolve()),
                sha256=sha256(inference_dir / "decisions.jsonl"),
                record_id=decision["id"],
                step=decision["step"],
                group_id=decision["group_id"],
            ),
        )
    rows = [
        r
        for r in pq.read_table(input_dir / mentions_name).to_pylist()
        if r["page_id"] in pages
    ]
    if len(rows) != selected["original_rows"] or {r["page_id"] for r in rows} != pages:
        raise ValueError("Original mention coverage differs from frozen scope")
    revisions = {tuple(r) for r in selected["used_revisions"]}
    if {(r["page_id"], r["revision_id"]) for r in rows} != revisions:
        raise ValueError("Original mention revisions differ from frozen scope")
    groups = [
        g
        for g in _jsonl(input_dir / matching / "groups.jsonl")
        if g["page_id"] in pages
    ]
    exact_path = input_dir / matching / "exact_pairs.parquet"
    exact = [
        p
        for p in pq.read_table(exact_path).to_pylist()
        if p.get(
            "page_id",
            next((g["page_id"] for g in groups if g["id"] == p["group_id"]), None),
        )
        in pages
    ]
    for pair in exact:
        pair.update(
            run_id=run_id,
            decision_reference=dict(
                path=str(exact_path.resolve()),
                sha256=sha256(exact_path),
                record_id=pair["group_id"],
            ),
        )
    pairs = exact + pairs
    tables = mentions_populate(
        rows,
        groups,
        pairs,
        input_sha256=manifest["original_input_sha256"],
        dataset_namespace=manifest["original_input_sha256"],
        stage=stage,
        scoped_inventory=scoped_inventory,
    )
    records_path, sources_path = (
        native_dir / "full_records.json.gz",
        native_dir / "sources.json",
    )
    bind(records_path)
    bind(sources_path)
    records, sources = read_json(records_path), read_json(sources_path)
    qids = {p["qid"] for p in pairs}
    if not qids <= records.keys() or not qids <= sources.keys():
        raise ValueError(
            f"Native acquisition pending: {sorted(qids - (records.keys() & sources.keys()))}"
        )
    tables["entities"] = entities_populate(
        groups,
        pairs,
        dataset_namespace=manifest["original_input_sha256"],
        input_sha256=manifest["original_input_sha256"],
        native_records=records,
        provenance=sources,
        stage=stage,
        scoped_inventory=scoped_inventory,
        **(
            {"eligible_group_ids": {g["id"] for g in groups}}
            if stage != "legacy"
            else {}
        ),
    )
    with tempfile.TemporaryDirectory(prefix="geoai-core-pages-") as directory:
        pages_run(input_dir, Path(directory) / "pages", pages)
        tables["wiki_pages"] = read_json(Path(directory) / "pages/wiki_pages.json.gz")
    page_keys = {
        (r["wiki_site"], r["wiki_page_id"], r["revision_id"])
        for r in tables["wiki_pages"]
    }
    if {(p[1], p[2]) for p in page_keys} != revisions:
        raise ValueError("Pages do not cover exactly the used revisions")
    entity_keys = {(r["entity_id"], r["type"]) for r in tables["entities"]}
    mids = {m["mention_id"] for m in tables["mentions"]}

    def original_values(row: dict) -> dict:
        if stage == "legacy":
            return row
        from GG_Data.pipeline.post_qid_mentions import ORIGINAL_FIELDS

        values = {k: row.get(k) for k in ORIGINAL_FIELDS}
        values["word"] = row.get(
            "raw_original_word", row.get("word_original", row["word"])
        )
        return values

    if len(mids) != len(rows) or any(
        m["raw"] != original_values(raw)
        or (m["wiki_site"], m["wiki_page_id"], m["revision_id"]) not in page_keys
        for m, raw in zip(tables["mentions"], rows)
    ):
        raise ValueError("Original mention values, identity or page FK changed")
    links = tables["mention_entity_links"]
    link_keys = {
        (link["mention_id"], link["entity_id"], link["entity_type"]) for link in links
    }
    if (
        len(link_keys) != len(links)
        or not {link["mention_id"] for link in links} <= mids
        or (stage == "legacy" and {link["mention_id"] for link in links} != mids)
        or any(
            (link["entity_id"], link["entity_type"]) not in entity_keys
            for link in links
        )
    ):
        raise ValueError("Mention bridge coverage, unique key or typed FK failed")
    _set_importance(tables)
    return _save_tables(
        output,
        tables,
        dict(
            status="CORE_COMPLETE_GEOGRAPHY_PENDING",
            scope=scope,
            processing_stage=stage,
            page_ids=sorted(pages),
            quality_status=readiness["quality_status"],
            locally_observed_readiness=observed,
            experimental_approval=signature.get("experimental_approval_sha256"),
            run_id=run_id,
            inputs=bindings,
            pending=["Events", "Relations", "Geography", "seven-table acceptance"],
            **_scoped_manifest(scoped_inventory_path, tables),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope-dir", type=Path)
    parser.add_argument("--core-dir", type=Path)
    parser.add_argument("--events-dir", type=Path)
    parser.add_argument("--inference-dir", type=Path)
    parser.add_argument("--native-dir", type=Path)
    parser.add_argument("--scoped-inventory", type=Path)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--training-dir", type=Path)
    parser.add_argument("--readiness-dir", type=Path)
    parser.add_argument("--experimental-approval", type=Path)
    parser.add_argument("--approval-manifest", type=Path)
    parser.add_argument("--matching-subdir", default="matching_k80_v2")
    parser.add_argument("--mentions-name", default="selected_mentions.parquet")
    parser.add_argument(
        "--stage",
        choices=("legacy", "pending", "exact", "model", "final"),
        default="legacy",
    )
    parser.add_argument("--scope", default="3", choices=("3", "10", "100"))
    args = parser.parse_args()
    if args.events_dir is not None:
        if args.core_dir is None:
            parser.error("Assembly requires --core-dir")
        assemble(args.core_dir, args.events_dir, args.output)
    elif args.stage in {"pending", "exact"}:
        if args.scope_dir is None:
            parser.error("Early stage requires --scope-dir")
        write_stage(
            args.input_dir,
            args.scope_dir,
            args.output,
            args.scope,
            args.stage,
            native_dir=args.native_dir,
            scoped_inventory_path=args.scoped_inventory,
        )
    elif args.inference_dir is not None:
        if args.scope_dir is None or args.native_dir is None:
            parser.error("Core build requires --scope-dir and --native-dir")
        build_core(
            args.input_dir,
            args.scope_dir,
            args.inference_dir,
            args.native_dir,
            args.output,
            args.scope,
            model_dir=args.model_dir,
            training_dir=args.training_dir,
            readiness_dir=args.readiness_dir,
            experimental_approval_path=args.experimental_approval,
            approval_manifest_path=args.approval_manifest,
            stage=args.stage,
            scoped_inventory_path=args.scoped_inventory,
        )
    else:
        prepare(
            args.input_dir,
            args.output,
            matching_subdir=args.matching_subdir,
            mentions_name=args.mentions_name,
        )


if __name__ == "__main__":
    main()

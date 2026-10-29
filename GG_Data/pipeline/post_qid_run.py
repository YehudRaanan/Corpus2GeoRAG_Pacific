"""Freeze nested page sets or build core tables from verified saved decisions.

Larger deliveries still require preceding acceptance and Geography decisions.
The core build does not run a model or populate Events, Relations or Geography.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
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
        found = {int(r["page_id"]) for r in rows if r["Source"] == title}
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
            ten.update(int(r["page_id"]) for r in rows if r["Source"] == title)
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


def prepare(input_dir: Path, output: Path) -> dict:
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
        "matching_k80_v2/groups.jsonl",
        "matching_k80_v2/jobs.jsonl",
        "matching_k80_v2/exact_pairs.parquet",
    ]
    manifest = dict(
        schema_version=1,
        original_input_sha256=selection["input_sha256"],
        selection_rule="Retained old pages first; fill ten in saved source_titles order. Three by ascending SHA256(20261029 NUL page_id) among retained pages. OWNER approved 2026-10-29.",
        scopes=scopes,
        inputs={name: sha256(input_dir / name) for name in inputs},
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "scope_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    # Subset immutable prepared questions; do not rerank or change candidate pools.
    source = input_dir / "matching_k80_v2/jobs.jsonl"
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


def build_core(
    input_dir: Path,
    scope_dir: Path,
    inference_dir: Path,
    native_dir: Path,
    output: Path,
    scope: str = "3",
    *,
    model_dir: Path | None = None,
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
    bindings = {}

    def bind(path: Path, expected: str | None = None) -> str:
        if not path.is_file():
            raise ValueError(f"Missing archived input: {path}")
        actual = sha256(path)
        if expected is not None and actual != expected:
            raise ValueError(f"Archived hash differs: {path}")
        bindings[str(path.resolve())] = actual
        return actual

    bind(scope_dir / "scope_manifest.json")
    manifest = read_json(scope_dir / "scope_manifest.json")
    required_inputs = {
        "selection.json",
        "selected_mentions.parquet",
        "revisions.parquet",
        "matching_k80_v2/groups.jsonl",
        "matching_k80_v2/jobs.jsonl",
        "matching_k80_v2/exact_pairs.parquet",
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
    bind(model_dir / "readiness.json", signature["readiness_sha256"])
    readiness = read_json(model_dir / "readiness.json")
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
    training_dir = input_dir / "training_k80_v2"
    for role, binding in readiness["files"].items():
        if role in code_names:
            continue
        if role.startswith("input:"):
            local = training_dir / role.removeprefix("input:")
        elif role == "public_manifest":
            local = training_dir / "public_manifest.json"
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
        approval_path = model_dir / "experimental_three_page_approval.json"
        bind(approval_path, signature["experimental_approval_sha256"])
        approval = read_json(approval_path)
        if not (
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
    all_jobs = _jsonl(input_dir / "matching_k80_v2/jobs.jsonl")
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
        for r in pq.read_table(input_dir / "selected_mentions.parquet").to_pylist()
        if r["page_id"] in pages
    ]
    if len(rows) != selected["original_rows"] or {r["page_id"] for r in rows} != pages:
        raise ValueError("Original mention coverage differs from frozen scope")
    revisions = {tuple(r) for r in selected["used_revisions"]}
    if {(r["page_id"], r["revision_id"]) for r in rows} != revisions:
        raise ValueError("Original mention revisions differ from frozen scope")
    groups = [
        g
        for g in _jsonl(input_dir / "matching_k80_v2/groups.jsonl")
        if g["page_id"] in pages
    ]
    exact_path = input_dir / "matching_k80_v2/exact_pairs.parquet"
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
    if len(mids) != len(rows) or any(
        m["raw"] != raw
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
        or {link["mention_id"] for link in links} != mids
        or any(
            (link["entity_id"], link["entity_type"]) not in entity_keys
            for link in links
        )
    ):
        raise ValueError("Mention bridge coverage, unique key or typed FK failed")
    occurrence_ids, source_pages = defaultdict(set), defaultdict(set)
    mention_pages = {m["mention_id"]: m["wiki_page_id"] for m in tables["mentions"]}
    for link in links:
        occurrence_ids[link["entity_id"]].add(link["mention_id"])
        source_pages[link["entity_id"]].add(mention_pages[link["mention_id"]])
    for entity in tables["entities"]:
        identity = entity["entity_id"]
        count = len(occurrence_ids[identity])
        entity.update(
            importance=count * len(source_pages[identity]),
            unique_original_mention_count=count,
            distinct_source_page_count=len(source_pages[identity]),
        )
        entity["attributes"]["importance_basis"] = dict(
            total_mentions=count,
            distinct_source_pages=len(source_pages[identity]),
            formula="unique original mention IDs per identity * distinct original source pages",
            status="LEGACY_COUNT_PRODUCT_WITH_TYPED_QID_DEDUPLICATION",
        )
        entity["attributes"]["normalized_mention_frequency"] = count / len(rows)
        entity["attributes"]["normalized_mention_frequency_denominator"] = len(rows)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=output.name + "-staging-", dir=output.parent
    ) as directory:
        stage = Path(directory) / "complete"
        stage.mkdir()
        for name, data in tables.items():
            with gzip.open(stage / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False)
        result = dict(
            status="CORE_COMPLETE_GEOGRAPHY_PENDING",
            scope=scope,
            page_ids=sorted(pages),
            quality_status=readiness["quality_status"],
            locally_observed_readiness=observed,
            experimental_approval=signature.get("experimental_approval_sha256"),
            run_id=run_id,
            inputs=bindings,
            counts={n: len(t) for n, t in tables.items()},
            pending=["Events", "Relations", "Geography", "seven-table acceptance"],
            outputs={p.name: sha256(p) for p in stage.glob("*.json.gz")},
        )
        (stage / "manifest.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        stage.rename(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope-dir", type=Path)
    parser.add_argument("--inference-dir", type=Path)
    parser.add_argument("--native-dir", type=Path)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--scope", default="3", choices=("3", "10", "100"))
    args = parser.parse_args()
    if args.inference_dir is not None:
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
        )
    else:
        prepare(args.input_dir, args.output)


if __name__ == "__main__":
    main()

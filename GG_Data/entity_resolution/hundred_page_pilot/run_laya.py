"""Prepare full saved pilot inputs on CPU; run joint Laya proposals separately.

The baseline is never an input to selection. Exact matches remain separate;
reverse coverage checks every eligible group, including assigned groups.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq

from GG_Data.entity_resolution.hundred_page_pilot.filter_qid_inventory import (
    compatible,
    source_allowed,
)
from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
    identity,
    matching_eligibility,
    prepare,
)
from GG_Data.entity_resolution.hundred_page_pilot.resolve_entities import (
    read_score_records,
)
from GG_Data.entity_resolution.laya_model.evaluate import (
    compare_pairs,
    is_max_choice,
    pair_key,
)
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256, write_jsonl

LOG = logging.getLogger(__name__)


def save_json(path: Path, value: dict) -> None:
    encoded = json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"Existing immutable output differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded)


def save_rows(path: Path, rows: list[dict]) -> None:
    if path.exists():
        if read_jsonl(path) != rows:
            raise ValueError(f"Existing immutable rows differ: {path}")
    else:
        write_jsonl(path, rows)


def model_entity(entity: dict) -> dict:
    titles = entity.get("linked_titles") or []
    name = (
        entity.get("model_name")
        or entity.get("label")
        or (titles[0] if titles else None)
    )
    if not name:
        raise ValueError(f"Inventory QID has no saved model name: {entity['qid']}")
    return dict(
        id=entity["qid"],
        name=name,
        aliases=entity.get("model_aliases", entity.get("aliases")) or titles[1:],
        description=entity.get("description") or "",
        model_name_basis=(
            "wikidata_label" if entity.get("label") else "saved_linked_title_fallback"
        ),
    )


def reverse_jobs(
    groups: list[dict], entities: list[dict], forward_pairs: list[dict]
) -> list[dict]:
    """Ask all eligible groups about uncovered QIDs on the same revision."""
    covered = {(p["page_id"], p["revision_id"], p["qid"]) for p in forward_pairs}
    by_revision = defaultdict(list)
    for entity in entities:
        key = (entity["page_id"], entity["revision_id"], entity["qid"])
        if key not in covered and source_allowed(entity):
            by_revision[key[:2]].append(entity)
    jobs = []
    for group in groups:
        candidates = [
            model_entity(e)
            for e in by_revision[group["page_id"], group["revision_id"]]
            if compatible(e, group["type"])
        ]
        if not candidates:
            continue
        jobs.append(
            dict(
                id=identity(["reverse", group["id"]]),
                direction="reverse",
                page_id=group["page_id"],
                revision_id=group["revision_id"],
                group_id=group["id"],
                entity=group,
                candidates=sorted(candidates, key=lambda e: e["id"]),
                total_local_candidates=len(candidates),
                excluded_count=0,
                provenance=dict(
                    group_id=group["id"],
                    source_row_indices=group.get("source_row_indices", []),
                    occurrence_ids=group.get("occurrence_ids", []),
                ),
            )
        )
    return jobs


def prepare_run(
    mentions: Path,
    entities: Path,
    scopes: Path,
    output: Path,
    candidate_count: int = 80,
) -> dict:
    """Freeze all cleaned rows, shared groups/exact/filter/ranked pools, and scopes."""
    if output.exists():
        raise FileExistsError(f"Preserve existing output: {output}")
    if candidate_count < 0:
        raise ValueError("Candidate count must be zero (all) or positive")
    source_paths = dict(mentions=mentions, entities=entities, scopes=scopes)
    source_hashes = {role: sha256(path) for role, path in source_paths.items()}
    table, inventory = pq.read_table(mentions), pq.read_table(entities)
    rows, entity_rows = table.to_pylist(), inventory.to_pylist()
    frozen = json.loads(scopes.read_text(encoding="utf-8"))
    frozen = frozen.get("scopes", frozen)
    allowed = {tuple(pair) for pair in frozen["100"]["used_revisions"]}
    actual = {(r["page_id"], r["revision_id"]) for r in rows}
    if actual != allowed or len({p for p, _ in actual}) != 100:
        raise ValueError("Use all saved 100-page / revision input scopes")
    for scope in (3, 10, 100):
        item = frozen[str(scope)]
        pairs = {tuple(pair) for pair in item["used_revisions"]}
        if (
            not pairs <= allowed
            or len(set(item["page_ids"])) != scope
            or {p for p, _ in pairs} != set(item["page_ids"])
        ):
            raise ValueError("Invalid frozen scope membership")
    entity_keys = [(e["page_id"], e["revision_id"], e["qid"]) for e in entity_rows]
    if (
        len(entity_keys) != len(set(entity_keys))
        or not {k[:2] for k in entity_keys} <= allowed
    ):
        raise ValueError("Inventory identities differ from saved revision scopes")
    for entity in entity_rows:
        if not all(
            k in entity
            for k in (
                "qid_source_status",
                "type_categories",
                "type_unknown",
                "qid_filter_policy_version",
            )
        ):
            raise ValueError("Use enriched shared filtered QID inventory")
        if not source_allowed(entity):
            raise ValueError("Filtered inventory contains excluded source QIDs")
        model = model_entity(entity)
        entity.update(
            model_name=model["name"],
            model_aliases=model["aliases"],
            model_name_basis=model["model_name_basis"],
        )
    output.mkdir(parents=True, exist_ok=False)
    pq.write_table(table, output / "mentions.parquet")
    pq.write_table(pa.Table.from_pylist(entity_rows), output / "entities.parquet")
    summary = prepare(
        output / "mentions.parquet",
        output / "entities.parquet",
        output / "forward",
        candidate_count,
        exclude_date=True,
    )
    jobs = read_jsonl(output / "forward/jobs.jsonl")
    for job in jobs:
        job["direction"] = "forward"
        job["provenance"] = dict(
            page_id=job["page_id"], revision_id=job["revision_id"], qid=job["qid"]
        )
    write_jsonl(output / "forward_jobs.jsonl", jobs)
    save_json(output / "scopes.json", frozen)
    if any(
        sha256(source_paths[role]) != digest for role, digest in source_hashes.items()
    ):
        raise ValueError("Source input changed during preparation")
    manifest = dict(
        schema_version=1,
        created_utc=datetime.now(timezone.utc).isoformat(),
        input_rows=len(rows),
        page_count=100,
        revision_scopes=len(actual),
        source_hashes=source_hashes,
        source_paths={k: str(v.resolve()) for k, v in source_paths.items()},
        forward_preparation=summary,
        candidate_count=candidate_count,
        exclude_date=True,
        source_policy=summary["source_policy"],
        assignments_changed=False,
        sequence="full eligible population forward; uncovered QIDs reverse against all eligible groups",
        active_work_seconds=None,
    )
    manifest["files"] = {
        str(p.relative_to(output)).replace("\\", "/"): sha256(p)
        for p in output.rglob("*")
        if p.is_file()
    }
    save_json(output / "manifest.json", manifest)
    return manifest


def scoped(rows: list[dict], scopes: dict, scope: int) -> list[dict]:
    allowed = {tuple(pair) for pair in scopes[str(scope)]["used_revisions"]}
    return [r for r in rows if (r["page_id"], r["revision_id"]) in allowed]


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def tokenizer_hashes(path: Path) -> dict:
    if not path.is_dir():
        raise ValueError("Expected a local tokenizer directory")
    hashes = {
        p.relative_to(path).as_posix(): sha256(p)
        for p in sorted(path.rglob("*"))
        if p.is_file()
    }
    if not hashes:
        raise ValueError("Local tokenizer directory is empty")
    return hashes


def load_local_tokenizer(path: Path):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(str(path), local_files_only=True)


def cache_binding(
    input_dir: Path, max_options: int, max_len: int, head_max_len: int
) -> dict:
    return dict(
        manifest_sha256=sha256(input_dir / "manifest.json"),
        model_code_sha256=sha256(Path(__file__).parents[1] / "laya_model/model.py"),
        max_options=max_options,
        max_len=max_len,
        head_max_len=head_max_len,
    )


def value_hash(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def capacity_failure(job: dict, direction: str, error: ValueError) -> dict | None:
    """Only the two canonical partition capacity errors are recoverable."""
    reason = str(error)
    candidate_id = None
    if reason != "Empty decision/query cannot fit token budget":
        matches = [
            c["id"]
            for c in job["candidates"]
            if reason
            == (
                f"Candidate {c['id']!r} cannot fit without losing option name, instruction or non-context evidence"
            )
        ]
        if len(matches) != 1:
            return None
        candidate_id = matches[0]
    record = dict(
        id=job["id"],
        direction=direction,
        page_id=job.get("page_id"),
        revision_id=job.get("revision_id"),
        status="NOT_RUN_INPUT_CAPACITY",
        candidate_id=candidate_id,
        error_reason=reason,
        job_sha256=value_hash(job),
    )
    return dict(record, failure_sha256=value_hash(record))


def validate_failure(job: dict, direction: str, record: dict) -> None:
    expected = capacity_failure(
        job, direction, ValueError(record.get("error_reason", ""))
    )
    if expected is None or expected != record:
        raise ValueError("Saved capacity failure differs from original job/reason")


def prepare_chunk_cache(
    input_dir: Path,
    tokenizer_path: Path,
    output: Path,
    *,
    max_options: int = 20,
    max_len: int = 1024,
    head_max_len: int = 256,
    prefix_cache: Path | None = None,
    prefix_receipt: Path | None = None,
) -> dict:
    """Stream forward partitions on CPU using local tokenizer files, no weights."""
    from GG_Data.entity_resolution.laya_model.model import (
        partition_record,
        validate_prepared_chunks,
    )

    if output.exists():
        raise FileExistsError(f"Preserve existing output: {output}")
    if max_options < 1 or head_max_len < 32 or max_len <= head_max_len:
        raise ValueError("Invalid decision token/option budgets")
    binding = cache_binding(input_dir, max_options, max_len, head_max_len)
    hashes = tokenizer_hashes(tokenizer_path)
    source = input_dir / "forward_jobs.jsonl"
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    source_hash = manifest["files"]["forward_jobs.jsonl"]
    if sha256(source) != source_hash:
        raise ValueError("Prepared forward jobs changed")
    tokenizer = load_local_tokenizer(tokenizer_path)
    prefix_path = prefix_cache / "forward_chunks.jsonl" if prefix_cache else None
    prefix_hash = sha256(prefix_path) if prefix_path else None
    receipt_path = None
    prefix_provenance = None
    if prefix_path is not None:
        receipt_path = prefix_receipt or prefix_cache / "inputs.json"
        prefix_provenance = json.loads(receipt_path.read_text(encoding="utf-8"))
        if prefix_provenance.get("binding") != binding:
            raise ValueError(
                "Prefix original binding differs from current inputs/code/budgets"
            )
        if prefix_provenance.get("tokenizer_files") != hashes:
            raise ValueError("Prefix original tokenizer differs")
        if prefix_receipt is not None and (
            prefix_provenance.get("kind") != "retrospective_verified_prefix"
            or prefix_provenance.get("cache_sha256") != prefix_hash
            or not isinstance(prefix_provenance.get("jobs"), int)
        ):
            raise ValueError("Retrospective prefix receipt hash/count/kind differs")
    elif prefix_receipt is not None:
        raise ValueError("Prefix receipt requires a prefix cache")
    prefix = iter(iter_jsonl(prefix_path)) if prefix_path else iter(())
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "inputs.json", dict(binding=binding, tokenizer_files=hashes))
    seen, chunks_count, candidate_count = set(), 0, 0
    rejected_jobs = successful_candidates = prefix_jobs = 0

    def progress(status):
        value = dict(
            status=status,
            jobs=len(seen),
            chunks=chunks_count,
            candidates=candidate_count,
            rejected_jobs=rejected_jobs,
        )
        (output / "progress.json").write_text(
            json.dumps(value, indent=2), encoding="utf-8"
        )
        LOG.info("Forward chunk cache: %s", value)

    with (output / "forward_chunks.jsonl").open("x", encoding="utf-8") as stream:
        for job in iter_jsonl(source):
            if job["id"] in seen or job.get("direction") != "forward":
                raise ValueError("Expected unique forward job IDs")
            cached = next(prefix, None)
            if cached is not None:
                if cached.get("id") != job["id"] or "error" in cached:
                    raise ValueError(
                        "Prefix does not match original job order/successful evidence"
                    )
                chunks = cached["chunks"]
                validate_prepared_chunks(
                    job,
                    "forward",
                    chunks,
                    tokenizer=tokenizer,
                    max_options=max_options,
                    max_len=max_len,
                    head_max_len=head_max_len,
                )
                value = cached
                prefix_jobs += 1
            else:
                try:
                    chunks = partition_record(
                        job,
                        "forward",
                        tokenizer=tokenizer,
                        max_options=max_options,
                        max_len=max_len,
                        head_max_len=head_max_len,
                    )
                    value = dict(id=job["id"], chunks=chunks)
                except ValueError as error:
                    failure = capacity_failure(job, "forward", error)
                    if failure is None:
                        raise
                    chunks = []
                    value = dict(id=job["id"], error=failure)
                    rejected_jobs += 1
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")
            seen.add(job["id"])
            chunks_count += len(chunks)
            candidate_count += len(job["candidates"])
            if "error" not in value:
                successful_candidates += len(job["candidates"])
            if len(seen) % 100 == 0:
                stream.flush()
                progress("running")
    if next(prefix, None) is not None:
        raise ValueError("Prefix has extra rows beyond original jobs")
    if prefix_receipt is not None and prefix_jobs != prefix_provenance["jobs"]:
        raise ValueError("Retrospective prefix receipt job count differs")
    if (
        cache_binding(input_dir, max_options, max_len, head_max_len) != binding
        or tokenizer_hashes(tokenizer_path) != hashes
        or sha256(source) != source_hash
        or (prefix_path is not None and sha256(prefix_path) != prefix_hash)
        or (
            receipt_path is not None
            and json.loads(receipt_path.read_text(encoding="utf-8"))
            != prefix_provenance
        )
    ):
        raise ValueError("Chunk preparation inputs changed during execution")
    result = dict(
        schema_version=2,
        direction="forward",
        binding=binding,
        tokenizer_files=hashes,
        jobs=len(seen),
        chunks=chunks_count,
        candidates=candidate_count,
        successful_jobs=len(seen) - rejected_jobs,
        rejected_jobs=rejected_jobs,
        successful_candidates=successful_candidates,
        prefix_jobs=prefix_jobs,
        prefix_sha256=prefix_hash,
        prefix_receipt_sha256=sha256(receipt_path) if receipt_path else None,
        prefix_receipt_kind=(
            prefix_provenance.get("kind", "original_start_receipt")
            if prefix_provenance
            else None
        ),
        cache_sha256=sha256(output / "forward_chunks.jsonl"),
    )
    save_json(output / "manifest.json", result)
    progress("complete")
    return result


def load_chunk_cache(
    input_dir: Path,
    cache_dir: Path,
    checkpoint_binding: dict,
    selected_ids: set[str],
    *,
    max_options: int = 20,
    max_len: int = 1024,
    head_max_len: int = 256,
) -> dict[str, list[dict] | dict]:
    """Validate a complete cache once; retain only this scope's forward chunks."""
    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") not in (1, 2)
        or manifest.get("direction") != "forward"
        or manifest["binding"]
        != cache_binding(input_dir, max_options, max_len, head_max_len)
    ):
        raise ValueError("Forward chunk cache binding differs")
    hashes = {
        name.removeprefix("tokenizer/"): digest
        for name, digest in checkpoint_binding.get("checkpoint_files", {}).items()
        if name.startswith("tokenizer/")
    }
    if not hashes or hashes != manifest["tokenizer_files"]:
        raise ValueError("Forward chunk cache tokenizer differs from loaded checkpoint")
    path = cache_dir / "forward_chunks.jsonl"
    if sha256(path) != manifest["cache_sha256"]:
        raise ValueError("Forward chunk cache hash differs")
    jobs = iter(iter_jsonl(input_dir / "forward_jobs.jsonl"))
    seen, selected, chunks_count, candidate_count = set(), {}, 0, 0
    rejected_jobs = successful_candidates = 0
    for row in iter_jsonl(path):
        job = next(jobs, None)
        if job is None or row["id"] in seen or row["id"] != job["id"]:
            raise ValueError("Forward chunk cache job IDs differ")
        seen.add(row["id"])
        candidate_count += len(job["candidates"])
        if "error" in row:
            if manifest["schema_version"] == 1:
                raise ValueError("Schema1 cache cannot contain capacity error rows")
            validate_failure(job, "forward", row["error"])
            rejected_jobs += 1
            value = row["error"]
        else:
            chunks_count += len(row["chunks"])
            successful_candidates += sum(
                len(chunk["candidates"]) for chunk in row["chunks"]
            )
            value = row["chunks"]
        if row["id"] in selected_ids:
            selected[row["id"]] = value
    if (
        next(jobs, None) is not None
        or set(selected) != selected_ids
        or len(seen) != manifest["jobs"]
        or chunks_count != manifest["chunks"]
        or candidate_count != manifest["candidates"]
        or (
            manifest["schema_version"] == 1 and successful_candidates != candidate_count
        )
        or (
            manifest["schema_version"] == 2
            and (
                successful_candidates != manifest["successful_candidates"]
                or rejected_jobs != manifest["rejected_jobs"]
                or len(seen) - rejected_jobs != manifest["successful_jobs"]
            )
        )
    ):
        raise ValueError("Incomplete forward chunk cache counts/coverage")
    return selected


def run_scope(
    input_dir: Path,
    output: Path,
    agent,
    scope: int,
    *,
    max_seconds: float,
    checkpoint_binding: dict,
    baseline: list[dict] | None = None,
    max_options: int = 20,
    max_len: int = 1024,
    head_max_len: int = 256,
    chunk_cache: Path | None = None,
) -> dict:
    """Save complete question traces after every joint removal loop; resumable."""
    from GG_Data.entity_resolution.laya_model.model import choose_remaining

    if scope not in (3, 10, 100) or not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError("Expected saved 3/10/100 scope and positive execution cap")
    if not (output / "inputs.json").exists() and any(
        (output / name).exists()
        for name in (
            "forward_traces.jsonl",
            "reverse_traces.jsonl",
            "forward_not_run.jsonl",
            "reverse_not_run.jsonl",
            "proposals.jsonl",
            "summary.json",
        )
    ):
        raise ValueError("Saved inference has no original binding receipt")
    started = time.monotonic()
    manifest_path = input_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        if sha256(input_dir / name) != digest:
            raise ValueError(f"Prepared input changed: {name}")
    scopes = json.loads((input_dir / "scopes.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    save_json(
        output / "inputs.json",
        dict(
            manifest_sha256=sha256(manifest_path),
            scope=scope,
            checkpoint_binding=checkpoint_binding,
            code_sha256=sha256(Path(__file__)),
            model_code_sha256=sha256(Path(__file__).parents[1] / "laya_model/model.py"),
            max_options=max_options,
            max_len=max_len,
            head_max_len=head_max_len,
            chunk_cache_manifest_sha256=(
                sha256(chunk_cache / "manifest.json") if chunk_cache else None
            ),
        ),
    )
    groups = scoped(read_jsonl(input_dir / "forward/groups.jsonl"), scopes, scope)
    entities = scoped(
        pq.read_table(input_dir / "entities.parquet").to_pylist(), scopes, scope
    )
    forward = scoped(read_jsonl(input_dir / "forward_jobs.jsonl"), scopes, scope)
    cached_chunks = (
        load_chunk_cache(
            input_dir,
            chunk_cache,
            checkpoint_binding,
            {j["id"] for j in forward},
            max_options=max_options,
            max_len=max_len,
            head_max_len=head_max_len,
        )
        if chunk_cache
        else None
    )
    exact = scoped(
        pq.read_table(input_dir / "forward/exact_pairs.parquet").to_pylist(),
        scopes,
        scope,
    )
    group_by_id = {g["id"]: g for g in groups}
    entity_by_key = {(e["page_id"], e["revision_id"], e["qid"]): e for e in entities}

    def check_budget():
        if (output / "STOP").exists() or time.monotonic() - started >= max_seconds:
            raise TimeoutError("Execution cap/STOP reached; completed traces preserved")

    job_model_called = False

    def guarded_score(*args, **kwargs):
        nonlocal job_model_called
        check_budget()
        job_model_called = True
        return agent.system_one(*args, **kwargs)

    bounded_agent = SimpleNamespace(tok=agent.tok, system_one=guarded_score)

    def decisions(jobs: list[dict], direction: str) -> list[dict]:
        nonlocal job_model_called
        path = output / f"{direction}_traces.jsonl"
        failure_path = output / f"{direction}_not_run.jsonl"
        saved = read_score_records(path)
        by_id = {r["id"]: r for r in saved}
        failures = read_score_records(failure_path)
        failed = {r["id"]: r for r in failures}
        job_by_id = {j["id"]: j for j in jobs}
        if len(by_id) != len(saved) or not by_id.keys() <= {j["id"] for j in jobs}:
            raise ValueError("Saved traces differ from current jobs")
        if (
            len(failed) != len(failures)
            or not failed.keys() <= job_by_id.keys()
            or by_id.keys() & failed.keys()
        ):
            raise ValueError("Saved failures differ from current jobs/traces")
        for job_id, failure in failed.items():
            validate_failure(job_by_id[job_id], direction, failure)
            if (
                direction == "forward"
                and cached_chunks is not None
                and cached_chunks[job_id] != failure
            ):
                raise ValueError("Saved failure differs from bound cache reason")

        def progress(status, include_ids=False):
            state = dict(
                status=status,
                direction=direction,
                questions=len(jobs),
                completed_questions=len(by_id),
                not_run_questions=len(jobs) - len(by_id),
                input_capacity_not_run_questions=len(failed),
                pending_questions=len(jobs) - len(by_id) - len(failed),
                elapsed_seconds=time.monotonic() - started,
                active_work_seconds=None,
            )
            if include_ids:
                state["not_run_ids"] = [j["id"] for j in jobs if j["id"] not in by_id]
            (output / "progress.json").write_text(
                json.dumps(state, indent=2), encoding="utf-8"
            )

        progress("running")
        with path.open("a", encoding="utf-8") as stream, failure_path.open(
            "a", encoding="utf-8"
        ) as failure_stream:
            for job in jobs:
                if job["id"] in by_id or job["id"] in failed:
                    continue
                cached = (
                    cached_chunks[job["id"]]
                    if direction == "forward" and cached_chunks is not None
                    else None
                )
                if isinstance(cached, dict):
                    validate_failure(job, direction, cached)
                    failure_stream.write(json.dumps(cached, ensure_ascii=False) + "\n")
                    failure_stream.flush()
                    failed[job["id"]] = cached
                    continue
                job_model_called = False
                try:
                    check_budget()
                    trace = choose_remaining(
                        bounded_agent,
                        job,
                        direction,
                        max_options=max_options,
                        max_len=max_len,
                        head_max_len=head_max_len,
                        **({"prepared_chunks": cached} if cached is not None else {}),
                    )
                except TimeoutError:
                    progress("resource_limit", include_ids=True)
                    raise
                except ValueError as error:
                    failure = (
                        capacity_failure(job, direction, error)
                        if not job_model_called
                        else None
                    )
                    # Capacity recovery is limited to partition_record, before inference.
                    traceback = error.__traceback__
                    partition_error = False
                    while traceback is not None:
                        partition_error |= (
                            traceback.tb_frame.f_code.co_name == "partition_record"
                        )
                        traceback = traceback.tb_next
                    if failure is None or not partition_error:
                        raise
                    failure_stream.write(json.dumps(failure, ensure_ascii=False) + "\n")
                    failure_stream.flush()
                    failed[job["id"]] = failure
                    continue
                value = dict(
                    id=job["id"],
                    direction=direction,
                    page_id=job["page_id"],
                    revision_id=job["revision_id"],
                    trace=trace,
                )
                validate_trace(job, value)
                stream.write(json.dumps(value, ensure_ascii=False) + "\n")
                stream.flush()
                by_id[job["id"]] = value
                if len(by_id) % 50 == 0:
                    progress("running")
        progress("direction_complete", include_ids=True)
        for job in jobs:
            if job["id"] in by_id:
                validate_trace(job, by_id[job["id"]])
        return [by_id[j["id"]] if j["id"] in by_id else failed[j["id"]] for j in jobs]

    def proposals(jobs: list[dict], traces: list[dict], direction: str) -> list[dict]:
        pairs = []
        for job, trace in zip(jobs, traces):
            if trace.get("status") == "NOT_RUN_INPUT_CAPACITY":
                continue
            for step in trace["trace"]:
                candidate_id = step["candidate_id"]
                if candidate_id is None:
                    continue
                gid, qid = (
                    (candidate_id, job["qid"])
                    if direction == "forward"
                    else (job["group_id"], candidate_id)
                )
                group = group_by_id[gid]
                entity = entity_by_key[job["page_id"], job["revision_id"], qid]
                pairs.append(
                    dict(
                        page_id=job["page_id"],
                        revision_id=job["revision_id"],
                        group_id=gid,
                        qid=qid,
                        method=f"experimental_laya_{direction}",
                        record_id=job["id"],
                        source_row_indices=group["source_row_indices"],
                        occurrence_ids=group["occurrence_ids"],
                        context_sources=group["context_sources"],
                        source_review_statuses=group["source_review_statuses"],
                        entity_provenance=entity,
                        decision=step,
                    )
                )
        return pairs

    forward_traces = decisions(forward, "forward")
    forward_pairs = exact + proposals(forward, forward_traces, "forward")
    save_rows(output / "forward_pairs.jsonl", forward_pairs)
    reverse = reverse_jobs(groups, entities, forward_pairs)
    save_rows(output / "reverse_jobs.jsonl", reverse)
    reverse_traces = decisions(reverse, "reverse")
    reverse_pairs = proposals(reverse, reverse_traces, "reverse")
    save_rows(output / "reverse_pairs.jsonl", reverse_pairs)
    combined = {pair_key(p): p for p in forward_pairs + reverse_pairs}
    pairs = [combined[k] for k in sorted(combined)]
    save_rows(output / "proposals.jsonl", pairs)
    rows = scoped(
        pq.read_table(input_dir / "mentions.parquet").to_pylist(), scopes, scope
    )
    failures = [
        r
        for r in forward_traces + reverse_traces
        if r.get("status") == "NOT_RUN_INPUT_CAPACITY"
    ]
    not_run_ids = {r["id"] for r in failures}
    result = accounting(
        rows,
        groups,
        entities,
        forward,
        reverse,
        pairs,
        manifest["source_policy"],
        not_run_ids,
    )
    result.update(
        scope=scope,
        status="complete_with_not_run" if failures else "complete",
        assignments_changed=False,
        elapsed_seconds=time.monotonic() - started,
        active_work_seconds=None,
        inference_questions=len(forward) + len(reverse),
        completed_questions=len(forward) + len(reverse) - len(failures),
        not_run_questions=len(failures),
        not_run_ids=sorted(not_run_ids),
        not_run_by_direction=dict(Counter(r["direction"] for r in failures)),
        comparison=(
            compare_pairs(pairs, scoped(baseline, scopes, scope))
            if baseline is not None
            else None
        ),
        limitation="Experimental proposals; public annotations incomplete; no pilot gold accuracy claim.",
    )
    # Elapsed duration varies on verification/resume, so retain first completed receipt.
    summary_path = output / "summary.json"
    if summary_path.exists():
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
        if {k: v for k, v in saved.items() if k != "elapsed_seconds"} != {
            k: v for k, v in result.items() if k != "elapsed_seconds"
        }:
            raise ValueError("Completed summary differs from current proposals")
        return saved
    save_json(summary_path, result)
    (output / "progress.json").write_text(
        json.dumps(
            dict(
                status=result["status"],
                not_run_questions=len(failures),
                not_run_ids=sorted(not_run_ids),
            )
        ),
        encoding="utf-8",
    )
    return result


def validate_trace(job: dict, value: dict) -> None:
    allowed = {c["id"] for c in job["candidates"]}
    selected = [
        s["candidate_id"] for s in value["trace"] if s["candidate_id"] is not None
    ]
    if len(selected) != len(set(selected)) or not set(selected) <= allowed:
        raise ValueError("Joint traces contain repeated or stale candidate identities")
    if not value["trace"] or value["id"] != job["id"]:
        raise ValueError("Missing complete joint question trace")
    chunks = defaultdict(list)
    chunk_counts = {step["chunk_count"] for step in value["trace"]}
    if len(chunk_counts) != 1 or next(iter(chunk_counts)) < 1:
        raise ValueError("Invalid complete chunk count")
    for step in value["trace"]:
        chunks[step["chunk_index"]].append(step)
    if set(chunks) != set(range(next(iter(chunk_counts)))):
        raise ValueError("Incomplete chunk coverage")
    if {
        identity for steps in chunks.values() for identity in steps[0]["remaining_ids"]
    } != allowed:
        raise ValueError("Incomplete retained-pool coverage")
    presented = set()
    for steps in chunks.values():
        if steps[-1]["candidate_id"] is not None or any(
            s["candidate_id"] is None for s in steps[:-1]
        ):
            raise ValueError("Missing complete chunk STOP")
        initial = steps[0]["remaining_ids"]
        if len(initial) != len(set(initial)) or presented & set(initial):
            raise ValueError("Duplicate chunk coverage")
        presented.update(initial)
        remaining = list(initial)
        for step in steps:
            if step["remaining_ids"] != remaining:
                raise ValueError("Incomplete removal trace")
            options, probabilities = step["option_ids"], step["probabilities"]
            if (
                set(options.values()) != set(remaining) | {None}
                or len(options) != len(remaining) + 1
                or step["choice"] not in options
                or options[step["choice"]] != step["candidate_id"]
                or step["stop"] != (step["candidate_id"] is None)
                or probabilities.keys() != options.keys()
                or any(
                    not math.isfinite(float(p)) or not 0 <= float(p) <= 1
                    for p in probabilities.values()
                )
                or sum(probabilities.values()) <= 0
                or not is_max_choice(probabilities, step["choice"])
            ):
                raise ValueError("Invalid saved option probabilities or choice")
            if step["candidate_id"] is not None:
                if step["candidate_id"] not in remaining:
                    raise ValueError("Invalid complete removal trace")
                remaining.remove(step["candidate_id"])
    if presented != allowed:
        raise ValueError("Incomplete retained-pool coverage")


def accounting(
    rows,
    groups,
    entities,
    forward,
    reverse,
    pairs,
    source_policy,
    not_run_ids=frozenset(),
):
    assigned = {p["group_id"] for p in pairs}
    exposed_forward = {
        c["id"] for j in forward if j["id"] not in not_run_ids for c in j["candidates"]
    }
    exposed_reverse = {j["group_id"] for j in reverse if j["id"] not in not_run_ids}
    exposed = exposed_forward | exposed_reverse | assigned
    eligible_indices = {i for g in groups for i in g["source_row_indices"]}
    assigned_indices = {
        i for g in groups if g["id"] in assigned for i in g["source_row_indices"]
    }
    not_presented_indices = {
        i for g in groups if g["id"] not in exposed for i in g["source_row_indices"]
    }
    reasons = Counter(
        matching_eligibility(r, source_policy, exclude_date=True)[1] for r in rows
    )
    qid_counts, group_counts = Counter(), Counter()
    for p in pairs:
        qid_counts[p["page_id"], p["revision_id"], p["qid"]] += 1
        group_counts[p["group_id"]] += 1
    return dict(
        input_rows=len(rows),
        eligible_occurrences=len(eligible_indices),
        eligible_groups=len(groups),
        assigned_mentions=len(assigned_indices),
        assigned_groups=len(assigned),
        unresolved_mentions=len(eligible_indices - assigned_indices),
        excluded_rows=reasons["source_excluded"],
        date_deferred_rows=reasons["deferred_date"],
        eligibility_reason_counts=dict(reasons),
        not_presented_mentions=len(not_presented_indices),
        not_presented_groups=len(set(g["id"] for g in groups) - exposed),
        not_run_questions=0,
        inventory_qid_revision_rows=len(entities),
        covered_qid_revision_rows=len(qid_counts),
        uncovered_qid_revision_rows=len(entities) - len(qid_counts),
        groups_with_multiple_qids=sum(n > 1 for n in group_counts.values()),
        qids_with_multiple_groups=sum(n > 1 for n in qid_counts.values()),
        proposal_pairs=len(pairs),
        forward_jobs=len(forward),
        reverse_jobs=len(reverse),
        retained_forward_candidate_pairs=sum(len(j["candidates"]) for j in forward),
        retrieval_omitted_forward_candidate_pairs=sum(
            j["excluded_count"] for j in forward
        ),
        review_groups=sum(bool(g["review_source_row_indices"]) for g in groups),
        previously_eligible_groups=sum(
            bool(g["previously_eligible_source_row_indices"]) for g in groups
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prep = commands.add_parser("prepare", help="CPU-only; does not import/load Laya")
    for name in ("mentions", "entities", "scopes", "output"):
        prep.add_argument("--" + name, type=Path, required=True)
    prep.add_argument("--candidate-count", type=int, default=80)
    cache = commands.add_parser(
        "prepare-chunks", help="CPU-only forward cache; local tokenizer, no weights"
    )
    for name in ("input-dir", "tokenizer", "output"):
        cache.add_argument("--" + name, type=Path, required=True)
    cache.add_argument("--prefix-cache", type=Path)
    cache.add_argument("--prefix-receipt", type=Path)
    for name, default in (
        ("max-options", 20),
        ("max-len", 1024),
        ("head-max-len", 256),
    ):
        cache.add_argument("--" + name, type=int, default=default)
    score = commands.add_parser(
        "score", help="Use an already trained local Laya checkpoint"
    )
    for name in ("input-dir", "output", "checkpoint"):
        score.add_argument("--" + name, type=Path, required=True)
    score.add_argument("--scope", type=int, choices=(3, 10, 100), required=True)
    score.add_argument("--device", default="cuda")
    score.add_argument("--max-seconds", type=float, required=True)
    score.add_argument("--max-options", type=int, default=20)
    score.add_argument("--max-len", type=int, default=1024)
    score.add_argument("--head-max-len", type=int, default=256)
    score.add_argument("--baseline-pairs", type=Path)
    score.add_argument("--chunk-cache", type=Path)
    args = parser.parse_args()
    if args.action == "score":
        from GG_Data.entity_resolution.laya_model.evaluate import load_local_agent

        agent, binding = load_local_agent(args.checkpoint, args.device)
        result = run_scope(
            args.input_dir,
            args.output,
            agent,
            args.scope,
            max_seconds=args.max_seconds,
            checkpoint_binding=binding,
            baseline=read_jsonl(args.baseline_pairs) if args.baseline_pairs else None,
            max_options=args.max_options,
            max_len=args.max_len,
            head_max_len=args.head_max_len,
            chunk_cache=args.chunk_cache,
        )
        LOG.info("%s", json.dumps(result))
        return
    if args.action == "prepare-chunks":
        result = prepare_chunk_cache(
            args.input_dir,
            args.tokenizer,
            args.output,
            max_options=args.max_options,
            max_len=args.max_len,
            head_max_len=args.head_max_len,
            prefix_cache=args.prefix_cache,
            prefix_receipt=args.prefix_receipt,
        )
        LOG.info("%s", json.dumps(result))
        return
    result = prepare_run(
        args.mentions, args.entities, args.scopes, args.output, args.candidate_count
    )
    LOG.info(
        "%s",
        json.dumps(
            {k: result[k] for k in ("input_rows", "page_count", "revision_scopes")}
        ),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

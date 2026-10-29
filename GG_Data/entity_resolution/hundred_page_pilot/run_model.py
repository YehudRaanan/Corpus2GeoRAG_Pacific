"""Restore the approved fixed model, then run one manifest-bound pilot scope.

Use --setup for real CUDA restore evidence; then use --scope 3, 10 and 100.
All new receipts stay under --run-root. Training artifacts remain unchanged.
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import torch

from GG_Data.entity_resolution.decision_model import model as decision_model
from GG_Data.entity_resolution.hundred_page_pilot import readiness
from GG_Data.entity_resolution.hundred_page_pilot.resolve_entities import infer
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256

LOG = logging.getLogger(__name__)
APPROVAL_EVIDENCE = (
    "OWNER approved the 2026-10-30 revised pipeline plan "
    "docs/superpowers/plans/2026-10-30-revised-pipeline-new-daniel-input.md, "
    "including fixed-model experimental 3/10/100 execution, at most 90 new GPU "
    "minutes within the existing aggregate $10 and six-hour limits."
)
LIMITATION = (
    "Experimental revised workflow only; held-out stop precision 278/311 misses "
    "90 percent. No new quality pass or Daniel accuracy claim."
)
ROLES = {
    "training_complete": "training_complete.json",
    "training_selection": "training_selection.json",
    "validation_metrics": "final_validation_metrics.json",
    "held_out_metrics": "final_public_test_metrics.json",
}


def save(path: Path, value: dict) -> None:
    """Reuse identical immutable evidence; fail before replacing different bytes."""
    encoded = json.dumps(value, indent=2).encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"Existing immutable output differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded)


def validate_jobs(scope: int, path: Path, manifest: dict) -> list[dict]:
    jobs = read_jsonl(path)
    allowed = {
        (row["page_id"], row["revision_id"]) for row in manifest["page_revisions"]
    }
    actual = {(job["page_id"], job["revision_id"]) for job in jobs}
    if (
        scope not in {3, 10, 100}
        or len({page for page, _ in actual}) != scope
        or not actual <= allowed
        or not {page for page, _ in actual} <= set(manifest["page_ids"])
        or any(
            type(value) is not int or value <= 0 for pair in actual for value in pair
        )
        or len({job["id"] for job in jobs}) != len(jobs)
    ):
        raise ValueError(
            f"Jobs differ from requested unique page/revision scope: {path}"
        )
    if manifest.get("schema_version") == 2:
        scope_path = path.parent / "scope_manifest.json"
        binding = manifest.get("scope_jobs", {}).get(str(scope), {})
        pages = sorted({page for page, _ in actual})
        if (
            not scope_path.is_file()
            or manifest.get("scope_manifest_sha256") != sha256(scope_path)
            or binding.get("sha256") != sha256(path)
            or binding.get("page_ids") != pages
        ):
            raise ValueError(f"Jobs differ from frozen scope binding: {path}")
        frozen = json.loads(scope_path.read_text(encoding="utf-8"))
        if frozen.get("scopes", {}).get(str(scope), {}).get("page_ids") != pages:
            raise ValueError(f"Job pages differ from frozen scope membership: {path}")
    return jobs


def bound_evidence(
    path: Path, expected: dict, timestamp: str, *, scores: int = 0
) -> dict | None:
    if not path.exists():
        return None
    saved = json.loads(path.read_text(encoding="utf-8"))
    extra = {timestamp, "scores"} if scores else {timestamp}
    if {key: value for key, value in saved.items() if key not in extra} != expected:
        raise ValueError(f"Existing evidence has stale bindings: {path}")
    datetime.fromisoformat(saved[timestamp])
    if scores and (
        not isinstance(saved.get("scores"), list)
        or len(saved["scores"]) != scores
        or not all(
            type(value) in (int, float) and math.isfinite(value)
            for value in saved["scores"]
        )
    ):
        raise ValueError(f"Existing restore scores are invalid: {path}")
    return saved


def setup(
    run_root: Path, scope_dir: Path, training_root: Path, model_dir: Path
) -> dict:
    """Inspect actual weights and execute the canonical loader/scorer on CUDA."""
    manifest_path = run_root / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = model_dir / "full_best.pt"
    jobs_path = scope_dir / "jobs_3.jsonl"
    paths = {role: model_dir / name for role, name in ROLES.items()}
    paths.update(readiness.CODE_FILES)
    paths["public_manifest"] = training_root / "public_manifest.json"
    for path in (checkpoint, jobs_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    public = json.loads(paths["public_manifest"].read_text(encoding="utf-8"))
    for name, expected in public["files"].items():
        path = training_root / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Missing or stale training input: {path}")
    job = validate_jobs(3, jobs_path, manifest)[0]
    digest = sha256(checkpoint)
    if digest != manifest["files"]["train_20261029/full_best.pt"]["sha256"]:
        raise ValueError("Checkpoint differs from approved manifest")
    if not torch.cuda.is_available():
        raise RuntimeError("Actual restore setup requires CUDA")
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False, mmap=True)
    inspected = dict(
        checkpoint_sha256=digest,
        head_only=saved["head_only"],
        has_encoder_weights=any(key.startswith("encoder.") for key in saved["model"]),
        encoder_optimizer_steps=saved["progress"]["encoder_optimizer_steps"],
        input_hashes=saved["input_hashes"],
        model_id=saved["model_id"],
        revision=saved["revision"],
        source_hashes_at_inspection={
            role: sha256(paths[role]) for role in ("training_code", "model_code")
        },
        final_artifact_hashes={
            role: sha256(model_dir / name) for role, name in ROLES.items()
        },
        limitation="Current code binding after file separation; training-time source immutability remains unproved.",
    )
    evidence = run_root / "model_readiness"
    inspection_path, restore_path = (
        evidence / "checkpoint_inspection.json",
        evidence / "restore_check.json",
    )
    old = bound_evidence(inspection_path, inspected, "inspected_at")
    restore_binding = dict(
        checkpoint_sha256=digest,
        loader=readiness.LOADER,
        model_id=decision_model.MODEL,
        revision=decision_model.REVISION,
        tokenizer_revision=decision_model.REVISION,
        model_code_sha256=sha256(paths["model_code"]),
        job_id=job["id"],
        jobs_sha256=sha256(jobs_path),
        manifest_sha256=sha256(manifest_path),
        metadata={
            **{key: saved[key] for key in ("model_id", "revision", "progress")},
            "inference_dtype": "bfloat16_autocast",
        },
    )
    restored = bound_evidence(
        restore_path, restore_binding, "checked_at", scores=len(job["candidates"]) + 1
    )
    del saved
    save(
        inspection_path,
        old or {**inspected, "inspected_at": datetime.now(timezone.utc).isoformat()},
    )
    if restored is None:
        scorer, tokenizer, metadata = decision_model.load_scorer(checkpoint, "cuda")
        try:
            scores = decision_model.score_record(
                scorer, tokenizer, job, device="cuda", pair_batch_size=16
            )
            expected_ids = {candidate["id"] for candidate in job["candidates"]} | {None}
            if (
                metadata != restore_binding["metadata"]
                or scores.keys() != expected_ids
                or not all(
                    type(value) in (int, float) and math.isfinite(value)
                    for value in scores.values()
                )
            ):
                raise ValueError("Actual restore metadata or scores/options differ")
            save(
                restore_path,
                {
                    **restore_binding,
                    "scores": list(scores.values()),
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        finally:
            del scorer, tokenizer
            gc.collect()
            torch.cuda.empty_cache()
    paths.update(checkpoint_inspection=inspection_path, restore_check=restore_path)
    result = readiness.build_readiness(checkpoint, paths, training_root)
    if result["technical_status"] != "PASS":
        raise ValueError(result["technical_errors"])
    save(evidence / "readiness.json", result)
    return result


def run_scope(
    scope: int,
    run_root: Path,
    scope_dir: Path,
    training_root: Path,
    model_dir: Path,
    *,
    max_hours: float = 1.2,
) -> dict:
    """Run or verify one scope with the fixed checkpoint and current approval."""
    if (
        type(max_hours) not in (int, float)
        or not math.isfinite(max_hours)
        or not 0 < max_hours <= 1.2
    ):
        raise ValueError("Inference max_hours must be positive and at most 1.2 hours")
    manifest_path = run_root / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint, jobs_path = (
        model_dir / "full_best.pt",
        scope_dir / f"jobs_{scope}.jsonl",
    )
    jobs = validate_jobs(scope, jobs_path, manifest)
    if sha256(checkpoint) != manifest["files"]["train_20261029/full_best.pt"]["sha256"]:
        raise ValueError("Checkpoint differs from approved manifest")
    directory = run_root / f"scope_{scope}"
    receipt_path = directory / "experimental_approval.json"
    approval = dict(
        approved_by="OWNER",
        scope="experimental_source_name_pilot",
        decision="Allow the exploratory source-name pilot with this model",
        checkpoint_sha256=sha256(checkpoint),
        jobs_sha256=sha256(jobs_path),
        page_ids=sorted({job["page_id"] for job in jobs}),
        manifest={
            "path": str(manifest_path.resolve()),
            "sha256": sha256(manifest_path),
        },
        approval_evidence=APPROVAL_EVIDENCE,
        limitation=LIMITATION,
    )
    readiness.validate_experimental_scope(approval, checkpoint, jobs_path)
    readiness_path = run_root / "model_readiness/readiness.json"
    # Validate the intended training root before creating a new scope receipt.
    ready = json.loads(readiness_path.read_text(encoding="utf-8"))
    if Path(ready["input_directory"]).resolve() != training_root.resolve():
        raise ValueError("Readiness training root differs from launcher input")
    save(receipt_path, approval)
    readiness.validate_readiness(
        readiness_path,
        checkpoint,
        experimental_approval=receipt_path,
        jobs_path=jobs_path,
    )
    inference = directory / "inference"
    summary_path = inference / "inference_summary.json"
    if summary_path.exists():
        signature = dict(
            jobs_sha256=sha256(jobs_path),
            checkpoint_sha256=sha256(checkpoint),
            readiness_sha256=sha256(readiness_path),
            experimental_approval_sha256=sha256(receipt_path),
        )
        if (
            json.loads(
                (inference / "inference_inputs.json").read_text(encoding="utf-8")
            )
            != signature
        ):
            raise ValueError("Completed inference bindings differ")
        from GG_Data.entity_resolution.hundred_page_pilot.report import (
            _completed_model_pairs,
        )

        selected = _completed_model_pairs(jobs, inference)
        actual = {
            (pair["page_id"], pair["revision_id"], pair["group_id"], pair["qid"])
            for pair in read_jsonl(inference / "model_pairs.jsonl")
        }
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if (
            any(summary.get(key) != value for key, value in signature.items())
            or selected != actual
            or summary.get("questions") != len(jobs)
            or summary.get("selected_pairs") != len(actual)
        ):
            raise ValueError("Completed inference summary/pairs differ from scores")
    else:
        try:
            summary = infer(
                jobs_path,
                checkpoint,
                inference,
                max_hours,
                16,
                "cuda",
                readiness_path=readiness_path,
                require_readiness=True,
                experimental_approval_path=receipt_path,
            )
            save(summary_path, summary)
        finally:
            gc.collect()
            torch.cuda.empty_cache()
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-root", "scope-dir", "training-root", "model-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--setup", action="store_true")
    action.add_argument("--scope", type=int, choices=(3, 10, 100))
    parser.add_argument("--max-hours", type=float, default=1.2)
    args = parser.parse_args()
    paths = (args.run_root, args.scope_dir, args.training_root, args.model_dir)
    result = (
        setup(*paths)
        if args.setup
        else run_scope(args.scope, *paths, max_hours=args.max_hours)
    )
    LOG.info(
        "%s",
        json.dumps(
            {
                key: result.get(key)
                for key in (
                    "technical_status",
                    "quality_status",
                    "questions",
                    "selected_pairs",
                )
            }
        ),
    )


if __name__ == "__main__":
    main()

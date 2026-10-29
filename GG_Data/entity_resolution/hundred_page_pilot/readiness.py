"""Hash-bound promotion gate over final training files and root restore evidence.

The inspection and restore receipts must come from actual checkpoint inspection
and load_scorer/score_record execution. This module does not execute a model or
turn positive-only Daniel references into precision truth.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from GG_Data.entity_resolution.decision_model.model import (
    MODEL,
    REVISION,
    STOP_SENTENCE,
)
from GG_Data.entity_resolution.luke_pilot.data import sha256

PIPELINE_DIRECTORY = Path(__file__).parent
TRAINING_DIRECTORY = PIPELINE_DIRECTORY.parent / "decision_model"
CODE_FILES = {
    "training_code": TRAINING_DIRECTORY / "train.py",
    "inference_code": PIPELINE_DIRECTORY / "resolve_entities.py",
    "model_code": TRAINING_DIRECTORY / "model.py",
    "readiness_code": Path(__file__),
}
# post_qid_run executes a checksum-verified archived gate with runpy. Its source
# files live together in that immutable archive, not in the current package tree.
if __name__ == "<run_path>":
    CODE_FILES = {
        role: PIPELINE_DIRECTORY / path.name for role, path in CODE_FILES.items()
    }
LOADER = "decision_model.model.load_scorer"
REQUIRED_FILES = {
    *CODE_FILES,
    "training_complete",
    "training_selection",
    "public_manifest",
    "validation_metrics",
    "held_out_metrics",
    "checkpoint_inspection",
    "restore_check",
}


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _quality(metrics: dict) -> dict:
    total, accuracy = metrics.get("states"), metrics.get("set_choice_accuracy")
    correct = None
    if (
        type(total) is int
        and total > 0
        and type(accuracy) in (int, float)
        and math.isfinite(accuracy)
        and 0 <= accuracy <= 1
    ):
        candidate = round(total * accuracy)
        if math.isclose(candidate, total * accuracy, rel_tol=0, abs_tol=1e-7):
            correct = candidate
    stops, true_stops = metrics.get("predicted_stops"), metrics.get("correct_stops")
    stop_valid = (
        type(stops) is int
        and type(true_stops) is int
        and 0 <= true_stops <= stops
        and type(total) is int
        and stops <= total
    )
    passed = (
        correct is not None
        and correct / total >= 0.9
        and stop_valid
        and stops > 0
        and true_stops / stops >= 0.9
    )
    return {
        "selection": {"correct": correct, "total": total},
        "selection_numerator_source": "derived from saved set_choice_accuracy times states",
        "stop_precision": {
            "correct": true_stops if stop_valid else None,
            "total": stops if stop_valid else None,
        },
        "candidate_coverage": {
            k: metrics.get(k)
            for k in ("initial_pools", "retrieval_excluded_labelled_positive_groups")
        },
        "targets_pass": passed,
    }


def build_readiness(
    checkpoint: Path, paths: dict[str, Path], input_directory: Path
) -> dict:
    """Build pass/fail metadata; never retrain, select another model or waive quality.

    paths binds final source files, including root-produced checkpoint_inspection
    and restore_check JSON receipts. No readiness result replaces those receipts.
    """
    if not REQUIRED_FILES <= paths.keys():
        raise ValueError(
            f"Missing readiness files: {sorted(REQUIRED_FILES - paths.keys())}"
        )
    for role, expected_path in CODE_FILES.items():
        if paths[role].resolve() != expected_path.resolve():
            raise ValueError(f"Readiness must bind current {role}")
    complete, selection, inspected, restored, public = (
        _json(paths[role])
        for role in (
            "training_complete",
            "training_selection",
            "checkpoint_inspection",
            "restore_check",
            "public_manifest",
        )
    )
    digest = sha256(checkpoint)
    errors = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(complete.get("status") == "complete", "Training is unfinished")
    require(complete.get("head_stable") is True, "Warmup head stability is unproved")
    for record in (complete, inspected):
        require(
            record.get("model_id") == MODEL and record.get("revision") == REVISION,
            "Encoder identity differs from pinned model",
        )
        steps = record.get("encoder_optimizer_steps")
        require(
            type(steps) is int and steps > 0,
            "Actual encoder optimizer updates are missing",
        )
    require(
        inspected.get("head_only") is False
        and inspected.get("has_encoder_weights") is True,
        "Selected checkpoint does not contain tuned encoder weights",
    )
    require(
        inspected.get("checkpoint_sha256") == digest,
        "Inspected checkpoint hash differs",
    )
    for role in ("training_code", "model_code"):
        require(
            inspected.get("source_hashes_at_inspection", {}).get(role)
            == sha256(paths[role]),
            f"Inspected remote source differs or is unbound: {role}",
        )
    for role in (
        "training_complete",
        "training_selection",
        "validation_metrics",
        "held_out_metrics",
    ):
        require(
            inspected.get("final_artifact_hashes", {}).get(role) == sha256(paths[role]),
            f"Final artifact is not bound to inspected checkpoint: {role}",
        )
    require(
        complete.get("final_checkpoint")
        == selection.get("final_checkpoint")
        == checkpoint.name,
        "Selected checkpoint differs from training selection",
    )
    require(
        selection.get("selection_basis") == "validation marginal set loss only"
        and selection.get("public_test_not_used_for_selection") is True,
        "Validation-only selection evidence is missing",
    )
    require(
        restored.get("checkpoint_sha256") == digest
        and restored.get("loader") == LOADER,
        "Actual inference-loader restore evidence is missing or for another checkpoint",
    )
    require(
        restored.get("model_code_sha256") == sha256(paths["model_code"]),
        "Restore check used different inference model code",
    )
    require(
        restored.get("model_id") == MODEL
        and restored.get("revision") == REVISION
        and restored.get("tokenizer_revision") == REVISION,
        "Restore tokenizer/encoder revision differs",
    )
    scores = restored.get("scores")
    require(
        isinstance(scores, list)
        and bool(scores)
        and all(type(v) in (int, float) and math.isfinite(v) for v in scores),
        "Restore finite-score check is missing or failed",
    )
    inputs = complete.get("input_hashes", {})
    require(
        inspected.get("input_hashes") == inputs,
        "Checkpoint training input/config differs",
    )
    require(
        isinstance(inputs.get("training_config"), str)
        and bool(inputs["training_config"]),
        "Training configuration is missing",
    )
    expected_inputs = {
        **public.get("files", {}),
        "public_manifest.json": sha256(paths["public_manifest"]),
    }
    require(
        {k: v for k, v in inputs.items() if k != "training_config"} == expected_inputs,
        "Frozen training manifest differs from completion evidence",
    )
    files = {
        role: {"path": str(path.resolve()), "sha256": sha256(path)}
        for role, path in paths.items()
    }
    for name, expected in expected_inputs.items():
        path = input_directory / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Stale training input: {name}")
        files[f"input:{name}"] = {"path": str(path.resolve()), "sha256": expected}
    quality = {
        "validation": _quality(_json(paths["validation_metrics"])),
        "held_out": _quality(_json(paths["held_out_metrics"])),
        "daniel_precision": "NOT_EVALUATED_POSITIVE_ONLY_REFERENCE",
        "daniel_stop_precision": "NOT_EVALUATED_POSITIVE_ONLY_REFERENCE",
    }
    return {
        "schema_version": 1,
        "checkpoint_sha256": digest,
        "input_directory": str(input_directory.resolve()),
        "files": files,
        "model_id": MODEL,
        "encoder_revision": REVISION,
        "tokenizer_revision": REVISION,
        "stop_sentence": STOP_SENTENCE,
        "technical_status": "FAIL" if errors else "PASS",
        "provenance": {
            "training_time_code_immutability": "NOT_PROVEN",
            "code_identity_basis": "REMOTE_SOURCE_BYTES_AT_POST_TRAINING_INSPECTION",
            "metric_checkpoint_association": "ROOT_FINAL_ARTIFACT_INSPECTION",
            "limitation": "Original checkpoint and metrics do not embed training-time code hashes or metric checkpoint IDs",
        },
        "technical_errors": errors,
        "quality": quality,
        "quality_status": (
            "PASS_PUBLIC_TARGETS"
            if all(quality[k]["targets_pass"] for k in ("validation", "held_out"))
            else "FAIL_OR_UNKNOWN"
        ),
    }


def validate_readiness(
    path: Path | None,
    checkpoint: Path,
    *,
    experimental_approval: Path | None = None,
    jobs_path: Path | None = None,
) -> dict:
    """Fail closed before inference writes outputs or loads model weights."""
    if path is None or not path.is_file():
        raise ValueError("Model readiness file is required")
    saved = _json(path)
    if saved.get("checkpoint_sha256") != sha256(checkpoint):
        raise ValueError("Stale readiness checkpoint")
    files = saved.get("files", {})
    if not REQUIRED_FILES <= files.keys():
        raise ValueError("Missing readiness file bindings")
    for role, binding in files.items():
        source = Path(binding["path"])
        if not source.is_file() or sha256(source) != binding["sha256"]:
            raise ValueError(f"Stale readiness file: {role}")
    current = build_readiness(
        checkpoint,
        {k: Path(v["path"]) for k, v in files.items() if not k.startswith("input:")},
        Path(saved["input_directory"]),
    )
    if saved != current:
        raise ValueError("Stale or altered readiness metadata")
    if current["technical_status"] != "PASS":
        raise ValueError(f"Technical readiness failed: {current['technical_errors']}")
    if current["quality_status"] != "PASS_PUBLIC_TARGETS":
        if experimental_approval is None or jobs_path is None:
            raise ValueError(
                "Quality readiness failed or unknown; OWNER disposition is required"
            )
        approval = _json(experimental_approval)
        pages = {
            json.loads(line)["page_id"]
            for line in jobs_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        if not (
            approval.get("approved_by") == "OWNER"
            and approval.get("scope") == "experimental_three_pages"
            and approval.get("decision")
            == "Allow the experimental three-page run with this model"
            and approval.get("checkpoint_sha256") == sha256(checkpoint)
            and approval.get("jobs_sha256") == sha256(jobs_path)
            and len(pages) == 3
            and pages == set(approval.get("page_ids", []))
        ):
            raise ValueError(
                "Experimental approval does not cover this checkpoint and three-page input"
            )
    return current

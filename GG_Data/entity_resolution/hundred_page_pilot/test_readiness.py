"""Readiness tests use inspection receipts, never download encoder weights."""

import json
from pathlib import Path

import pytest

from GG_Data.entity_resolution.hundred_page_pilot import readiness
from GG_Data.entity_resolution.luke_pilot.data import sha256


@pytest.fixture
def evidence(tmp_path):
    checkpoint = tmp_path / "full_best.pt"
    checkpoint.write_bytes(b"fixture checkpoint; not real weights")
    digest = sha256(checkpoint)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "train.jsonl").write_text("training fixture", encoding="utf-8")
    hashes = {"train.jsonl": sha256(inputs / "train.jsonl")}
    manifest = {"files": hashes}
    (inputs / "public_manifest.json").write_text(json.dumps(manifest))
    hashes = {**hashes, "public_manifest.json": sha256(inputs / "public_manifest.json"),
              "training_config": '{"max_length": 256}'}
    common = {"model_id": readiness.MODEL, "revision": readiness.REVISION,
              "input_hashes": hashes}
    documents = {
        "training_complete": {**common, "status": "complete", "head_stable": True,
                              "encoder_optimizer_steps": 7, "final_checkpoint": checkpoint.name},
        "training_selection": {"final_checkpoint": checkpoint.name,
                               "selection_basis": "validation marginal set loss only",
                               "public_test_not_used_for_selection": True},
        "validation_metrics": {"states": 10, "set_choice_accuracy": .9,
                               "predicted_stops": 10, "correct_stops": 9,
                               "initial_pools": 5, "retrieval_excluded_labelled_positive_groups": 1},
        "held_out_metrics": {"states": 20, "set_choice_accuracy": .95,
                             "predicted_stops": 10, "correct_stops": 9,
                             "initial_pools": 8, "retrieval_excluded_labelled_positive_groups": 2},
        "checkpoint_inspection": {**common, "checkpoint_sha256": digest,
                                  "head_only": False, "has_encoder_weights": True,
                                  "encoder_optimizer_steps": 5},
        "restore_check": {"checkpoint_sha256": digest, "model_id": readiness.MODEL,
                          "revision": readiness.REVISION, "tokenizer_revision": readiness.REVISION,
                          "loader": "hundred_page_pilot.model.load_scorer",
                          "scores": [.2, -.3]},
    }
    documents["restore_check"]["model_code_sha256"] = sha256(Path(readiness.__file__).with_name("model.py"))
    paths = {"public_manifest": inputs / "public_manifest.json"}
    for role, value in documents.items():
        path = tmp_path / f"{role}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[role] = path
    directory = Path(readiness.__file__).parent
    paths.update({"training_code": directory / "train.py", "inference_code": directory / "match.py",
                  "model_code": directory / "model.py", "readiness_code": directory / "readiness.py"})
    inspected = documents["checkpoint_inspection"]
    inspected["source_hashes_at_inspection"] = {
        role: sha256(paths[role]) for role in ("training_code", "model_code")}
    inspected["final_artifact_hashes"] = {
        role: sha256(paths[role]) for role in
        ("training_complete", "training_selection", "validation_metrics", "held_out_metrics")}
    paths["checkpoint_inspection"].write_text(json.dumps(inspected))
    return checkpoint, paths, inputs


def test_readiness_separates_public_targets_and_daniel_unknown(evidence):
    checkpoint, paths, inputs = evidence
    result = readiness.build_readiness(checkpoint, paths, inputs)
    assert result["technical_status"] == "PASS"
    assert result["quality_status"] == "PASS_PUBLIC_TARGETS"
    assert result["quality"]["held_out"]["selection"] == {"correct": 19, "total": 20}
    assert result["quality"]["daniel_precision"] == "NOT_EVALUATED_POSITIVE_ONLY_REFERENCE"
    path = checkpoint.parent / "readiness.json"
    path.write_text(json.dumps(result))
    assert readiness.validate_readiness(path, checkpoint) == result
    checkpoint.write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="checkpoint"):
        readiness.validate_readiness(path, checkpoint)


@pytest.mark.parametrize("role,field,value", [
    ("training_complete", "status", "running"),
    ("training_complete", "head_stable", False),
    ("checkpoint_inspection", "head_only", True),
    ("checkpoint_inspection", "has_encoder_weights", False),
    ("checkpoint_inspection", "encoder_optimizer_steps", 0),
    ("restore_check", "scores", [float("nan")]),
    ("restore_check", "tokenizer_revision", "changed"),
    ("restore_check", "model_code_sha256", "changed"),
    ("training_selection", "final_checkpoint", "frozen_best.pt"),
])
def test_technical_failures_cannot_promote(evidence, role, field, value):
    checkpoint, paths, inputs = evidence
    document = json.loads(paths[role].read_text())
    document[field] = value
    paths[role].write_text(json.dumps(document))
    result = readiness.build_readiness(checkpoint, paths, inputs)
    assert result["technical_status"] == "FAIL"
    path = checkpoint.parent / "readiness.json"
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="Technical readiness"):
        readiness.validate_readiness(path, checkpoint)


def test_failed_quality_unknown_stop_and_stale_input_reject(evidence):
    checkpoint, paths, inputs = evidence
    metrics = json.loads(paths["held_out_metrics"].read_text())
    metrics.update(predicted_stops=0, correct_stops=0)
    paths["held_out_metrics"].write_text(json.dumps(metrics))
    inspected = json.loads(paths["checkpoint_inspection"].read_text())
    inspected["final_artifact_hashes"]["held_out_metrics"] = sha256(paths["held_out_metrics"])
    paths["checkpoint_inspection"].write_text(json.dumps(inspected))
    result = readiness.build_readiness(checkpoint, paths, inputs)
    assert result["quality_status"] == "FAIL_OR_UNKNOWN"
    path = checkpoint.parent / "readiness.json"
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="Quality readiness"):
        readiness.validate_readiness(path, checkpoint)
    (inputs / "train.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="Stale"):
        readiness.validate_readiness(path, checkpoint)


def test_gate_runs_before_model_load_or_output_creation(tmp_path):
    from GG_Data.entity_resolution.hundred_page_pilot.match import infer

    output = tmp_path / "output"
    with pytest.raises(ValueError, match="readiness"):
        infer(tmp_path / "jobs", tmp_path / "checkpoint", output, 1, 8, "cpu",
              require_readiness=True)
    assert not output.exists()


def test_experimental_argument_alone_requires_readiness(tmp_path):
    from GG_Data.entity_resolution.hundred_page_pilot.match import infer

    with pytest.raises(ValueError, match="readiness"):
        infer(tmp_path / "jobs", tmp_path / "checkpoint", tmp_path / "output", 1, 8, "cpu",
              experimental_approval_path=tmp_path / "approval.json")


def test_changed_bound_evidence_and_forged_pass_reject(evidence):
    checkpoint, paths, inputs = evidence
    result = readiness.build_readiness(checkpoint, paths, inputs)
    path = checkpoint.parent / "readiness.json"
    result["quality"]["held_out"]["selection"]["correct"] = 20
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="altered"):
        readiness.validate_readiness(path, checkpoint)
    paths["restore_check"].write_text("{}")
    with pytest.raises(ValueError, match="Stale readiness file"):
        readiness.validate_readiness(path, checkpoint)


def test_owner_exception_is_bound_to_checkpoint_and_exact_three_page_jobs(evidence):
    checkpoint, paths, inputs = evidence
    metrics = json.loads(paths["held_out_metrics"].read_text())
    metrics.update(predicted_stops=10, correct_stops=8)
    paths["held_out_metrics"].write_text(json.dumps(metrics))
    inspection = json.loads(paths["checkpoint_inspection"].read_text())
    inspection["final_artifact_hashes"]["held_out_metrics"] = sha256(paths["held_out_metrics"])
    paths["checkpoint_inspection"].write_text(json.dumps(inspection))
    result = readiness.build_readiness(checkpoint, paths, inputs)
    path = checkpoint.parent / "readiness.json"
    path.write_text(json.dumps(result))
    jobs = checkpoint.parent / "jobs.jsonl"
    jobs.write_text('\n'.join(json.dumps({"page_id": p}) for p in [1, 2, 3]))
    approval = checkpoint.parent / "approval.json"
    approval.write_text(json.dumps(dict(approved_by="OWNER", scope="experimental_three_pages",
        checkpoint_sha256=sha256(checkpoint), jobs_sha256=sha256(jobs), page_ids=[1, 2, 3],
        decision="Allow the experimental three-page run with this model")))
    assert readiness.validate_readiness(path, checkpoint, experimental_approval=approval,
                                        jobs_path=jobs)["quality_status"] == "FAIL_OR_UNKNOWN"
    jobs.write_text(jobs.read_text() + '\n' + json.dumps({"page_id": 4}))
    with pytest.raises(ValueError, match="Experimental approval"):
        readiness.validate_readiness(path, checkpoint, experimental_approval=approval, jobs_path=jobs)


@pytest.mark.parametrize("field,role", [
    ("source_hashes_at_inspection", "training_code"),
    ("source_hashes_at_inspection", "model_code"),
    ("final_artifact_hashes", "validation_metrics"),
    ("final_artifact_hashes", "held_out_metrics"),
    ("final_artifact_hashes", "training_complete"),
    ("final_artifact_hashes", "training_selection"),
])
def test_unbound_or_other_run_sources_fail(evidence, field, role):
    checkpoint, paths, inputs = evidence
    inspected = json.loads(paths["checkpoint_inspection"].read_text())
    inspected[field][role] = "another run or different code"
    paths["checkpoint_inspection"].write_text(json.dumps(inspected))
    result = readiness.build_readiness(checkpoint, paths, inputs)
    assert result["technical_status"] == "FAIL"


def test_post_run_observation_does_not_claim_historical_training_code_proof(evidence):
    checkpoint, paths, inputs = evidence
    result = readiness.build_readiness(checkpoint, paths, inputs)
    assert result["provenance"]["training_time_code_immutability"] == "NOT_PROVEN"
    assert result["provenance"]["metric_checkpoint_association"] == "ROOT_FINAL_ARTIFACT_INSPECTION"

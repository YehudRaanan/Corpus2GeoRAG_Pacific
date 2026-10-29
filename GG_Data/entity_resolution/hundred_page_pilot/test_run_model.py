"""The model launcher binds real restore evidence before it reuses inference."""

import json

import pytest
import torch

from GG_Data.entity_resolution.decision_model import model
from GG_Data.entity_resolution.hundred_page_pilot import readiness
from GG_Data.entity_resolution.hundred_page_pilot import run_model
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256, write_jsonl


@pytest.fixture
def run_inputs(tmp_path, monkeypatch):
    run, scope_dir, training, models = (
        tmp_path / part for part in ("run", "scopes", "training", "models")
    )
    for directory in (run, scope_dir, training, models):
        directory.mkdir()
    write_jsonl(training / "train.jsonl", [{"fixture": True}])
    public = {"files": {"train.jsonl": sha256(training / "train.jsonl")}}
    (training / "public_manifest.json").write_text(json.dumps(public), encoding="utf-8")
    hashes = {
        **public["files"],
        "public_manifest.json": sha256(training / "public_manifest.json"),
        "training_config": "fixture only",
    }
    common = dict(model_id=model.MODEL, revision=model.REVISION, input_hashes=hashes)
    documents = {
        "training_complete.json": dict(
            **common,
            status="complete",
            head_stable=True,
            encoder_optimizer_steps=2,
            final_checkpoint="full_best.pt",
        ),
        "training_selection.json": dict(
            final_checkpoint="full_best.pt",
            selection_basis="validation marginal set loss only",
            public_test_not_used_for_selection=True,
        ),
        "final_validation_metrics.json": dict(
            states=10, set_choice_accuracy=0.9, predicted_stops=10, correct_stops=9
        ),
        "final_public_test_metrics.json": dict(
            states=10, set_choice_accuracy=0.9, predicted_stops=10, correct_stops=8
        ),
    }
    for name, value in documents.items():
        (models / name).write_text(json.dumps(value), encoding="utf-8")
    saved = dict(
        **common,
        head_only=False,
        model={"encoder.fixture": torch.tensor([1.0])},
        progress={"encoder_optimizer_steps": 2},
    )
    torch.save(saved, models / "full_best.pt")
    jobs = [
        dict(
            id=f"job-{i}",
            page_id=i,
            revision_id=i * 10,
            qid=f"Q{i}",
            excluded_count=0,
            entity={"name": "Fixture"},
            candidates=[
                dict(id=f"group-{i}", name="Fixture", type="LOC", context="Fixture")
            ],
        )
        for i in range(1, 4)
    ]
    write_jsonl(scope_dir / "jobs_3.jsonl", jobs)
    manifest = dict(
        page_ids=list(range(1, 101)),
        page_revisions=[dict(page_id=i, revision_id=i * 10) for i in range(1, 101)],
        files={
            "train_20261029/full_best.pt": {"sha256": sha256(models / "full_best.pt")}
        },
        original_mentions_sha256="a" * 64,
        source_reference_sha256="b" * 64,
    )
    (run / "input_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    metadata = {key: saved[key] for key in ("model_id", "revision", "progress")}
    metadata["inference_dtype"] = "bfloat16_autocast"

    def local_loader(checkpoint, device):
        if checkpoint != models / "full_best.pt" or device != "cuda":
            raise AssertionError("Launcher changed checkpoint or CUDA device")
        return object(), object(), metadata

    def local_score(scorer, tokenizer, job, *, device, pair_batch_size):
        if device != "cuda" or pair_batch_size != 16:
            raise AssertionError("Launcher changed approved device or pair batch size")
        return {**{candidate["id"]: 0.0 for candidate in job["candidates"]}, None: 1.0}

    monkeypatch.setattr(model, "load_scorer", local_loader)
    monkeypatch.setattr(model, "score_record", local_score)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    return run, scope_dir, training, models


def test_setup_and_scope_use_real_gate_and_leave_bound_experimental_outputs(run_inputs):
    run, scopes, training, models = run_inputs
    checked = run_model.setup(run, scopes, training, models)
    assert checked["technical_status"] == "PASS"
    assert checked["quality_status"] == "FAIL_OR_UNKNOWN"
    restored = json.loads(
        (run / "model_readiness/restore_check.json").read_text(encoding="utf-8")
    )
    assert restored["scores"] == [0.0, 1.0]
    assert restored["jobs_sha256"] == sha256(scopes / "jobs_3.jsonl")
    result = run_model.run_scope(3, run, scopes, training, models, max_hours=0.1)
    assert result["questions"] == 3 and result["selected_pairs"] == 0
    receipt = run / "scope_3/experimental_approval.json"
    readiness.validate_readiness(
        run / "model_readiness/readiness.json",
        models / "full_best.pt",
        experimental_approval=receipt,
        jobs_path=scopes / "jobs_3.jsonl",
    )
    approval = json.loads(receipt.read_text(encoding="utf-8"))
    assert "2026-10-30" in approval["approval_evidence"]
    assert approval["scope"] == "experimental_source_name_pilot"
    assert len(read_jsonl(run / "scope_3/inference/scores.jsonl")) == 3
    before = (run / "scope_3/inference/inference_summary.json").read_bytes()
    assert (
        run_model.run_scope(3, run, scopes, training, models, max_hours=0.1) == result
    )
    assert (run / "scope_3/inference/inference_summary.json").read_bytes() == before


@pytest.mark.parametrize("hours", [0, -1, 1.21, float("inf"), float("nan")])
def test_scope_rejects_unapproved_runtime_before_writing(run_inputs, hours):
    run, scopes, training, models = run_inputs
    with pytest.raises(ValueError, match="time|hours"):
        run_model.run_scope(3, run, scopes, training, models, max_hours=hours)
    assert not (run / "scope_3").exists()


def test_scope_cannot_use_jobs_from_unapproved_revision(run_inputs):
    run, scopes, training, models = run_inputs
    jobs = read_jsonl(scopes / "jobs_3.jsonl")
    jobs[0]["revision_id"] = 999
    (scopes / "jobs_3.jsonl").write_text(
        "".join(json.dumps(job) + "\n" for job in jobs), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="scope|revision"):
        run_model.setup(run, scopes, training, models)
    assert not (run / "model_readiness").exists()


def test_setup_cannot_create_restore_receipt_without_cuda(run_inputs, monkeypatch):
    run, scopes, training, models = run_inputs
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA"):
        run_model.setup(run, scopes, training, models)
    assert not (run / "model_readiness/restore_check.json").exists()


def test_stale_checkpoint_stops_before_model_receipts(run_inputs):
    run, scopes, training, models = run_inputs
    (models / "full_best.pt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Checkpoint|checkpoint"):
        run_model.setup(run, scopes, training, models)
    assert not (run / "model_readiness").exists()


def test_restore_rejects_missing_stop_score_instead_of_publishing_readiness(
    run_inputs, monkeypatch
):
    run, scopes, training, models = run_inputs
    monkeypatch.setattr(model, "score_record", lambda *args, **kwargs: {"group-1": 0.5})
    with pytest.raises(ValueError, match="scores|options"):
        run_model.setup(run, scopes, training, models)
    assert not (run / "model_readiness/restore_check.json").exists()
    assert not (run / "model_readiness/readiness.json").exists()


def test_completed_scope_rejects_changed_score_evidence(run_inputs):
    run, scopes, training, models = run_inputs
    run_model.setup(run, scopes, training, models)
    run_model.run_scope(3, run, scopes, training, models)
    (run / "scope_3/inference/scores.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="scores"):
        run_model.run_scope(3, run, scopes, training, models)


def test_completed_scope_rejects_stale_summary_bindings(run_inputs):
    run, scopes, training, models = run_inputs
    run_model.setup(run, scopes, training, models)
    run_model.run_scope(3, run, scopes, training, models)
    path = run / "scope_3/inference/inference_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["checkpoint_sha256"] = "0" * 64
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="summary|bindings"):
        run_model.run_scope(3, run, scopes, training, models)


@pytest.fixture
def revised_run_inputs(run_inputs):
    run, scopes, _, _ = run_inputs
    scope_manifest = {"scopes": {"3": {"page_ids": [1, 2, 3]}}}
    frozen_path = scopes / "scope_manifest.json"
    frozen_path.write_text(json.dumps(scope_manifest), encoding="utf-8")
    manifest_path = run / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        schema_version=2,
        scope_manifest_sha256=sha256(frozen_path),
        scope_jobs={
            "3": {"sha256": sha256(scopes / "jobs_3.jsonl"), "page_ids": [1, 2, 3]}
        },
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return run_inputs


def test_revised_scope_accepts_exact_frozen_jobs(revised_run_inputs):
    run, scopes, _, _ = revised_run_inputs
    jobs_path = scopes / "jobs_3.jsonl"
    manifest = json.loads((run / "input_manifest.json").read_text(encoding="utf-8"))
    assert run_model.validate_jobs(3, jobs_path, manifest) == read_jsonl(jobs_path)


def test_revised_scope_runs_only_the_manifest_bound_jobs(revised_run_inputs):
    run, scopes, training, models = revised_run_inputs
    run_model.setup(run, scopes, training, models)
    result = run_model.run_scope(3, run, scopes, training, models)
    assert result["questions"] == 3
    approval = json.loads(
        (run / "scope_3/experimental_approval.json").read_text(encoding="utf-8")
    )
    assert approval["jobs_sha256"] == sha256(scopes / "jobs_3.jsonl")


def test_revised_scope_rechecks_job_bytes_before_approval(revised_run_inputs):
    run, scopes, training, models = revised_run_inputs
    run_model.setup(run, scopes, training, models)
    jobs_path = scopes / "jobs_3.jsonl"
    jobs = read_jsonl(jobs_path)
    jobs[0]["qid"] = "Q999"
    jobs_path.write_text(
        "".join(json.dumps(job) + "\n" for job in jobs), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="frozen scope binding"):
        run_model.run_scope(3, run, scopes, training, models)
    assert not (run / "scope_3").exists()


@pytest.mark.parametrize(
    "change",
    [
        "candidate",
        "job_qid",
        "jobs_hash",
        "scope_hash",
        "scope_pages",
        "frozen_pages",
        "missing_scope",
    ],
)
def test_revised_scope_rejects_changed_frozen_binding_before_restore(
    revised_run_inputs, change
):
    run, scopes, training, models = revised_run_inputs
    manifest_path = run / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if change in {"candidate", "job_qid"}:
        jobs_path = scopes / "jobs_3.jsonl"
        jobs = read_jsonl(jobs_path)
        if change == "candidate":
            jobs[0]["candidates"][0]["context"] = "Changed same-scope context"
        else:
            jobs[0]["qid"] = "Q999"
        jobs_path.write_text(
            "".join(json.dumps(job) + "\n" for job in jobs), encoding="utf-8"
        )
    elif change == "jobs_hash":
        manifest["scope_jobs"]["3"]["sha256"] = "0" * 64
    elif change == "scope_hash":
        manifest["scope_manifest_sha256"] = "0" * 64
    elif change == "scope_pages":
        manifest["scope_jobs"]["3"]["page_ids"] = [1, 2, 4]
    elif change == "frozen_pages":
        frozen_path = scopes / "scope_manifest.json"
        frozen_path.write_text(
            json.dumps({"scopes": {"3": {"page_ids": [1, 2, 4]}}}),
            encoding="utf-8",
        )
        manifest["scope_manifest_sha256"] = sha256(frozen_path)
    else:
        del manifest["scope_jobs"]["3"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen|binding|scope"):
        run_model.setup(run, scopes, training, models)
    assert not (run / "model_readiness").exists()

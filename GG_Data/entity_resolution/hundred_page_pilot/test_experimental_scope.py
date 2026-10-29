"""The new pilot approval is separate from a model-quality decision."""

import json

import pytest

from GG_Data.entity_resolution.hundred_page_pilot import readiness
from GG_Data.entity_resolution.luke_pilot.data import sha256


def test_manifest_bound_pilot_approval_accepts_exact_subset_only(tmp_path):
    checkpoint, jobs, manifest = [
        tmp_path / n for n in ("model.pt", "jobs.jsonl", "manifest.json")
    ]
    checkpoint.write_bytes(b"saved checkpoint")
    jobs.write_text(
        "\n".join(json.dumps({"page_id": p, "revision_id": 11}) for p in range(10))
    )
    manifest.write_text(
        json.dumps(
            {
                "page_ids": list(range(100)),
                "page_revisions": [
                    {"page_id": p, "revision_id": 11} for p in range(100)
                ],
                "original_mentions_sha256": "a" * 64,
                "source_reference_sha256": "b" * 64,
            }
        )
    )
    approval = dict(
        approved_by="OWNER",
        scope="experimental_source_name_pilot",
        decision="Allow the exploratory source-name pilot with this model",
        checkpoint_sha256=sha256(checkpoint),
        jobs_sha256=sha256(jobs),
        page_ids=list(range(10)),
        manifest={"path": str(manifest), "sha256": sha256(manifest)},
        approval_evidence="OWNER instruction in current session; exploratory run only",
    )
    readiness.validate_experimental_scope(approval, checkpoint, jobs)
    saved_jobs = jobs.read_text()
    for revision in (99, None):
        jobs.write_text(
            "\n".join(
                json.dumps({"page_id": p, "revision_id": revision if p == 0 else 11})
                for p in range(10)
            )
        )
        with pytest.raises(ValueError, match="Experimental approval"):
            readiness.validate_experimental_scope(
                {**approval, "jobs_sha256": sha256(jobs)}, checkpoint, jobs
            )
    jobs.write_text(saved_jobs)
    for field, bad in [
        ("jobs_sha256", "bad"),
        ("checkpoint_sha256", "bad"),
        ("page_ids", list(range(9))),
        ("approval_evidence", ""),
    ]:
        with pytest.raises(ValueError, match="Experimental approval"):
            readiness.validate_experimental_scope(
                {**approval, field: bad}, checkpoint, jobs
            )
    manifest.write_text(manifest.read_text() + " ")
    with pytest.raises(ValueError, match="Experimental approval"):
        readiness.validate_experimental_scope(approval, checkpoint, jobs)


def test_old_three_page_approval_remains_exactly_scoped(tmp_path):
    checkpoint, jobs = tmp_path / "model.pt", tmp_path / "jobs.jsonl"
    checkpoint.write_bytes(b"checkpoint")
    jobs.write_text("\n".join(json.dumps({"page_id": p}) for p in (1, 2, 3)))
    approval = dict(
        approved_by="OWNER",
        scope="experimental_three_pages",
        decision="Allow the experimental three-page run with this model",
        checkpoint_sha256=sha256(checkpoint),
        jobs_sha256=sha256(jobs),
        page_ids=[1, 2, 3],
    )
    readiness.validate_experimental_scope(approval, checkpoint, jobs)
    jobs.write_text(jobs.read_text() + '\n{"page_id":4}')
    approval.update(jobs_sha256=sha256(jobs), page_ids=[1, 2, 3, 4])
    with pytest.raises(ValueError, match="Experimental approval"):
        readiness.validate_experimental_scope(approval, checkpoint, jobs)

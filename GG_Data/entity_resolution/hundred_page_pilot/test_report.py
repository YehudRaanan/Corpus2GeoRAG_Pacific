"""Export summaries count matched groups without creating empty matches."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import prepare
from GG_Data.entity_resolution.hundred_page_pilot.report import export
from GG_Data.entity_resolution.hundred_page_pilot.test_pipeline import entity, mention
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256, write_jsonl


def test_export_group_counts_exclude_unmatched_lookup_entries(tmp_path):
    rows = [
        mention(),
        mention(row=1),
        mention(name="Unknown", row=2),
        mention(name="1945", kind="DATE", row=3),
    ]
    mentions = tmp_path / "mentions.parquet"
    entities = tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    pq.write_table(pa.Table.from_pylist([entity()]), entities)
    matching, inference = tmp_path / "matching", tmp_path / "inference"
    summary = prepare(mentions, entities, matching, 80, exclude_date=True)
    (matching / "matching_summary.json").write_text(json.dumps(summary))
    inference.mkdir()
    jobs = read_jsonl(matching / "jobs.jsonl")
    (inference / "inference_inputs.json").write_text(
        json.dumps(
            {
                "jobs_sha256": sha256(matching / "jobs.jsonl"),
                "checkpoint_sha256": "a" * 64,
            }
        )
    )
    write_jsonl(inference / "model_pairs.jsonl", [])
    write_jsonl(
        inference / "scores.jsonl",
        [
            {
                "id": job["id"],
                "options": [
                    {"id": candidate["id"], "score": 0.0}
                    for candidate in job["candidates"]
                ]
                + [{"id": None, "score": 1.0}],
            }
            for job in jobs
        ],
    )
    reference = tmp_path / "reference.jsonl"
    reference.write_text("")
    result = export(mentions, matching, inference, reference, tmp_path / "export")

    assert result["groups"] == 2
    assert result["matched_groups"] == 1
    assert result["unresolved_resolved_page_groups"] == 1
    assert result["row_status_counts"] == {
        "MATCHED": 2,
        "UNRESOLVED_ENTITY": 1,
        "EXCLUDED_DATE": 1,
    }


def filtered_export_inputs(tmp_path):
    statuses = ["KEEP", "EXCLUDE", "REVIEW", "KEEP", "EXCLUDE", "KEEP"]
    rows = [
        mention(
            row=i,
            name="Unknown" if i == 3 else "1945" if i >= 4 else "Japan",
            kind="DATE" if i >= 4 else "LOC",
        )
        for i in range(6)
    ]
    rows = [
        {
            **r,
            "source_scope_status": status,
            "source_scope_policy_version": "article-source-v1",
            "source_scope_context": "clean context",
        }
        for r, status in zip(rows, statuses)
    ]
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    pq.write_table(pa.Table.from_pylist([entity()]), entities)
    matching, inference = tmp_path / "matching", tmp_path / "inference"
    summary = prepare(mentions, entities, matching, 80, exclude_date=True)
    (matching / "matching_summary.json").write_text(json.dumps(summary))
    inference.mkdir()
    jobs = read_jsonl(matching / "jobs.jsonl")
    (inference / "inference_inputs.json").write_text(
        json.dumps(
            {
                "jobs_sha256": sha256(matching / "jobs.jsonl"),
                "checkpoint_sha256": "a" * 64,
            }
        )
    )
    write_jsonl(inference / "model_pairs.jsonl", [])
    write_jsonl(
        inference / "scores.jsonl",
        [
            {
                "id": j["id"],
                "options": [{"id": c["id"], "score": 0.0} for c in j["candidates"]]
                + [{"id": None, "score": 1.0}],
            }
            for j in jobs
        ],
    )
    reference = tmp_path / "reference.jsonl"
    from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import identity

    # This anchor was recorded only in an excluded citation occurrence. It must
    # not become reference truth for an identically named eligible prose row.
    write_jsonl(
        reference,
        [
            dict(
                page_id=1,
                revision_id=11,
                group_id=identity([1, 11, "Japan", "LOC"]),
                qid="Q17",
                name="Japan",
                entity_group="LOC",
                source_row_index=1,
            )
        ],
    )
    return mentions, matching, inference, reference


def test_filtered_export_preserves_rows_and_separates_source_from_unresolved(tmp_path):
    inputs = filtered_export_inputs(tmp_path)
    result = export(*inputs, tmp_path / "export")
    rows = pq.read_table(tmp_path / "export/matched_mentions.parquet")
    assert rows.select(pq.read_table(inputs[0]).column_names).equals(
        pq.read_table(inputs[0])
    )
    assert rows["entity_match_status"].to_pylist() == [
        "MATCHED",
        "EXCLUDED_SOURCE",
        "REVIEW_SOURCE",
        "UNRESOLVED_ENTITY",
        "EXCLUDED_SOURCE",
        "EXCLUDED_DATE",
    ]
    assert rows["matched_qids"].to_pylist() == [["Q17"], [], [], [], [], []]
    assert pq.read_table(tmp_path / "export/unresolved_mentions.parquet")[
        "source_row_index"
    ].to_pylist() == [3]
    assert result["source_policy"] == "article-source-v1"
    assert result["reference_check"]["supported_positive_row_qid_pairs"] == 0
    assert result["source_scope_counts"] == {"KEEP": 3, "EXCLUDE": 2, "REVIEW": 1}


def test_export_rejects_source_policy_mismatch(tmp_path):
    inputs = filtered_export_inputs(tmp_path)
    summary_path = inputs[1] / "matching_summary.json"
    summary = json.loads(summary_path.read_text())
    summary["source_policy"] = "LEGACY_UNFILTERED"
    summary_path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="source policy"):
        export(*inputs, tmp_path / "export")


def test_export_rejects_excluded_group_membership(tmp_path):
    inputs = filtered_export_inputs(tmp_path)
    groups_path = inputs[1] / "groups.jsonl"
    groups = read_jsonl(groups_path)
    next(g for g in groups if g["name"] == "Japan")["source_row_indices"].append(1)
    groups_path.write_text("".join(json.dumps(g) + "\n" for g in groups))
    with pytest.raises(ValueError, match="source scope"):
        export(*inputs, tmp_path / "export")


def test_eligible_reference_expands_only_to_eligible_rows(tmp_path):
    inputs = filtered_export_inputs(tmp_path)
    reference = read_jsonl(inputs[3])
    reference[0]["source_row_index"] = 0
    inputs[3].write_text(json.dumps(reference[0]) + "\n")
    result = export(*inputs, tmp_path / "export")
    assert result["reference_check"]["supported_positive_row_qid_pairs"] == 1
    assert result["reference_check"]["recovered_supported_row_qid_pairs"] == 1


def test_export_requires_every_eligible_group(tmp_path):
    inputs = filtered_export_inputs(tmp_path)
    groups_path = inputs[1] / "groups.jsonl"
    groups = [g for g in read_jsonl(groups_path) if g["name"] != "Unknown"]
    groups_path.write_text("".join(json.dumps(g) + "\n" for g in groups))
    with pytest.raises(ValueError, match="source scope"):
        export(*inputs, tmp_path / "export")


def test_export_rejects_raw_candidate_context_in_filtered_job(tmp_path):
    inputs = filtered_export_inputs(tmp_path)
    jobs_path = inputs[1] / "jobs.jsonl"
    jobs = read_jsonl(jobs_path)
    jobs[0]["candidates"][0]["context"] = "citation metadata"
    jobs_path.write_text("".join(json.dumps(j) + "\n" for j in jobs))
    manifest_path = inputs[2] / "inference_inputs.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["jobs_sha256"] = sha256(jobs_path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Candidate text"):
        export(*inputs, tmp_path / "export")

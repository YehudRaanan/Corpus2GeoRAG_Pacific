"""Export summaries count matched groups without creating empty matches."""

import json

import pyarrow as pa
import pyarrow.parquet as pq

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

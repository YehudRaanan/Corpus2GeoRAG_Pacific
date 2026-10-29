"""Stable original rows anchor evaluation when repaired names change group IDs."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot import report
from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
    prepare,
    identity,
)
from GG_Data.entity_resolution.luke_pilot.data import sha256


def rows():
    return [
        dict(
            page_id=1,
            revision_id=11,
            source_row_index=i,
            word="Name",
            entity_group="PER",
            Text="Name",
            start=0,
            end=4,
        )
        for i in range(2)
    ]


def test_reference_expands_original_groups_after_names_change():
    source = [
        {
            **r,
            "word_original": "Name",
            "word": "Full Name",
            "matched_qids": ["Q1", "Q2"],
        }
        for r in rows()
    ]
    reference = [
        dict(
            page_id=1,
            revision_id=11,
            group_id=identity([1, 11, "Name", "PER"]),
            name="Name",
            entity_group="PER",
            source_row_index=0,
            qid="Q1",
        )
    ]
    result = report.original_row_reference_metrics(reference, source)
    assert result["supported_positive_row_qid_pairs"] == 2
    assert result["recovered_supported_row_qid_pairs"] == 2
    assert result["precision"] is None
    assert result["source_positive_recall"] == 1.0


def test_freezing_corrected_input_keeps_original_reference_names(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text("[[Name]]", encoding="utf-8")
    mention = {
        **rows()[0],
        "Text": "[[Name]]",
        "start": 2,
        "end": 6,
        "word": "Full Name",
        "word_original": "Name",
    }
    revision = dict(page_id=1, revision_id=11, wikitext_path=str(raw))
    link = dict(
        page_id=1,
        revision_id=11,
        qid="Q1",
        link_origin="RAW_DIRECT_LINK",
        anchor_text="Name",
        anchor_start=2,
        anchor_end=6,
    )
    reference = report.freeze_reference([mention], [revision], [link])
    assert reference[0]["name"] == "Name"
    assert reference[0]["group_id"] == identity([1, 11, "Name", "PER"])


def test_comparison_uses_original_rows_and_preserves_many_to_many(tmp_path):
    baseline, corrected = tmp_path / "baseline", tmp_path / "corrected"
    for folder in (baseline, corrected):
        folder.mkdir()
    before = [
        {**r, "matched_qids": ["Q1"] if r["source_row_index"] == 0 else []}
        for r in rows()
    ]
    after = [
        {
            **r,
            "word_original": "Name",
            "word": "Full Name",
            "repair_status": "repaired",
            "matched_qids": ["Q2", "Q3"] if r["source_row_index"] == 0 else ["Q1"],
        }
        for r in rows()
    ]
    for folder, data in ((baseline, before), (corrected, after)):
        pq.write_table(pa.Table.from_pylist(data), folder / "matched_mentions.parquet")
        (folder / "results.json").write_text(
            json.dumps(
                {
                    "exported_rows": 2,
                    "reference_sha256": "b" * 64,
                    "inference_complete": True,
                    "inference_inputs": {"checkpoint_sha256": "a" * 64},
                    "matching_summary": {"exclude_date": True},
                }
            )
        )
    result = report.compare_exports(baseline, corrected, tmp_path / "comparison")
    assert result["new_row_qid_pairs"] == 3
    assert result["lost_row_qid_pairs"] == 1
    assert result["newly_matched_rows"] == 1
    assert result["changed_qid_rows"] == 1
    assert result["corrected_multiple_qid_rows"] == 1
    assert result["corrected_repaired_rows"] == 2
    assert result["precision"] is None
    assert result["by_type"]["PER"]["new_row_qid_pairs"] == 3
    saved = json.loads((corrected / "results.json").read_text())
    (corrected / "results.json").write_text(
        json.dumps({**saved, "inference_complete": False})
    )
    with pytest.raises(ValueError, match="complete"):
        report.compare_exports(baseline, corrected, tmp_path / "incomplete")
    (corrected / "results.json").write_text(json.dumps(saved))
    (corrected / "results.json").write_text(
        json.dumps({**saved, "source_policy": "article-source-v1"})
    )
    with pytest.raises(ValueError, match="source policies"):
        report.compare_exports(baseline, corrected, tmp_path / "source_policy_scope")
    (corrected / "results.json").write_text(json.dumps(saved))
    baseline_saved = json.loads((baseline / "results.json").read_text())
    for folder, summary in ((baseline, baseline_saved), (corrected, saved)):
        (folder / "results.json").write_text(
            json.dumps({**summary, "inference_inputs": {}})
        )
    with pytest.raises(ValueError, match="checkpoint"):
        report.compare_exports(baseline, corrected, tmp_path / "unbound")
    (baseline / "results.json").write_text(json.dumps(baseline_saved))
    (corrected / "results.json").write_text(json.dumps(saved))
    for folder, summary in ((baseline, baseline_saved), (corrected, saved)):
        (folder / "results.json").write_text(
            json.dumps({**summary, "reference_sha256": None})
        )
    with pytest.raises(ValueError, match="reference"):
        report.compare_exports(baseline, corrected, tmp_path / "unbound_reference")
    (baseline / "results.json").write_text(json.dumps(baseline_saved))
    for scope in ({}, {"exclude_date": False}):
        (corrected / "results.json").write_text(
            json.dumps({**saved, "matching_summary": scope})
        )
        with pytest.raises(ValueError, match="DATE"):
            report.compare_exports(baseline, corrected, tmp_path / "date_scope")
    (corrected / "results.json").write_text(json.dumps(saved))
    changed = [{**after[0], "start": 1}, after[1]]
    pq.write_table(
        pa.Table.from_pylist(changed), corrected / "matched_mentions.parquet"
    )
    with pytest.raises(ValueError, match="original"):
        report.compare_exports(baseline, corrected, tmp_path / "bad")


def test_export_requires_all_scores_and_uses_original_reference(tmp_path):
    original = rows()
    original.append(
        {
            **original[0],
            "source_row_index": 2,
            "word": "1942",
            "entity_group": "DATE",
            "Text": "1942",
        }
    )
    corrected = [
        {
            **r,
            "word_original": r["word"],
            "word": "Full Name" if r["entity_group"] == "PER" else r["word"],
            "repair_status": "repaired" if r["entity_group"] == "PER" else "unchanged",
        }
        for r in original
    ]
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist(corrected), mentions)
    pq.write_table(
        pa.Table.from_pylist(
            [dict(page_id=1, revision_id=11, qid="Q1", label="Full Name")]
        ),
        entities,
    )
    matching, inference = tmp_path / "matching", tmp_path / "inference"
    matching.mkdir()
    inference.mkdir()
    summary = prepare(mentions, entities, matching, 80, exclude_date=True)
    (matching / "matching_summary.json").write_text(json.dumps(summary))
    job = json.loads((matching / "jobs.jsonl").read_text())
    candidate = job["candidates"][0]["id"]
    pair = {k: job[k] for k in ("id", "page_id", "revision_id", "qid")}
    (inference / "model_pairs.jsonl").write_text(
        json.dumps(
            {**pair, "group_id": candidate, "entity_group": "PER", "method": "model"}
        )
        + "\n"
    )
    (inference / "inference_inputs.json").write_text(
        json.dumps(
            {
                "jobs_sha256": sha256(matching / "jobs.jsonl"),
                "checkpoint_sha256": "a" * 64,
            }
        )
    )
    ref = tmp_path / "ref.jsonl"
    ref.write_text(
        json.dumps(
            dict(
                page_id=1,
                revision_id=11,
                group_id=identity([1, 11, "Name", "PER"]),
                name="Name",
                entity_group="PER",
                source_row_index=0,
                qid="Q1",
            )
        )
        + "\n"
    )
    with pytest.raises(ValueError, match="completed score"):
        report.export(mentions, matching, inference, ref, tmp_path / "partial")
    assert not (tmp_path / "partial").exists()
    (inference / "scores.jsonl").write_text(
        json.dumps(
            {
                "id": job["id"],
                "options": [
                    {"id": candidate, "score": 2.0},
                    {"id": None, "score": 0.0},
                ],
            }
        )
        + "\n"
    )
    result = report.export(mentions, matching, inference, ref, tmp_path / "final")
    assert result["reference_check"]["recovered_supported_row_qid_pairs"] == 2
    assert result["completed_questions"] == 1
    final = pq.read_table(tmp_path / "final" / "matched_mentions.parquet").to_pylist()
    assert final[2]["entity_match_status"] == "EXCLUDED_DATE"
    assert final[2]["matched_qids"] == []
    manifest_path = inference / "inference_inputs.json"
    saved_manifest = json.loads(manifest_path.read_text())
    manifest_path.write_text(json.dumps({"jobs_sha256": saved_manifest["jobs_sha256"]}))
    with pytest.raises(ValueError, match="checkpoint"):
        report.export(mentions, matching, inference, ref, tmp_path / "unbound")
    manifest_path.write_text(json.dumps(saved_manifest))
    (inference / "scores.jsonl").write_text("")
    with pytest.raises(ValueError, match="completed score"):
        report.export(mentions, matching, inference, ref, tmp_path / "missing")
    assert not (tmp_path / "missing").exists()

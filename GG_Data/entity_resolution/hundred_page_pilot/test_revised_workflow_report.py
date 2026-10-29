"""Workflow comparison keeps source-policy changes separate from matching changes."""

import gzip
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot import report
from GG_Data.entity_resolution.luke_pilot.data import sha256


def save_core(core, mentions, links, entities):
    core.mkdir(exist_ok=True)
    tables = {"mentions": mentions, "mention_entity_links": links, "entities": entities}
    for name, rows in tables.items():
        with gzip.open(core / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(rows, stream)
    manifest = {
        "counts": {name: len(rows) for name, rows in tables.items()},
        "outputs": {
            f"{name}.json.gz": sha256(core / f"{name}.json.gz") for name in tables
        },
        "stage": "final",
        "finalized": True,
    }
    (core / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def inputs(tmp_path):
    previous, core = tmp_path / "old", tmp_path / "core"
    previous.mkdir()
    original = []
    for index in range(6):
        original.append(
            dict(
                source_row_index=index,
                page_id=1,
                revision_id=10,
                entity_group="DATE" if index == 3 else "LOC",
                score=0.8,
                Text="[[Tokyo]]",
                start=0,
                end=9,
                word="[[Tokyo]]",
                Source="Tokyo page",
                Index=1,
                subtype=None,
                matched_qids=[f"Q{index + 1}"] if index in {1, 2, 4} else [],
                entity_match_status="EXCLUDED_DATE"
                if index == 3
                else "MATCHED"
                if index in {1, 2, 4}
                else "UNRESOLVED_ENTITY",
            )
        )
    pq.write_table(
        pa.Table.from_pylist(original), previous / "matched_mentions.parquet"
    )
    (previous / "results.json").write_text(
        json.dumps({"exported_rows": 6, "inference_complete": True}), encoding="utf-8"
    )
    statuses = [
        "ACCEPTED_EXACT",
        "ENTITY_UNRESOLVED",
        "SOURCE_EXCLUDED",
        "DEFERRED_DATE",
        "ACCEPTED_MODEL",
        "SOURCE_REVIEW",
    ]
    current = []
    for old, status in zip(original, statuses):
        raw = {
            key: old[key]
            for key in (
                "entity_group",
                "score",
                "word",
                "start",
                "end",
                "Source",
                "Index",
                "Text",
                "subtype",
            )
        }
        raw["Source"] = "Q1490"
        current.append(
            {
                **old,
                "raw": raw,
                "Source": "Q1490",
                "source_title": "Tokyo page",
                "source_page_qid": "Q1490",
                "word_original": "[[Tokyo]]",
                "raw_original_word": "[[Tokyo]]",
                "word": "Tokyo",
                "mention_id": f"new-{old['source_row_index']}",
                "matching_eligible": old["source_row_index"] in {0, 1, 4},
                "matching_eligibility_reason": "eligible"
                if old["source_row_index"] in {0, 1, 4}
                else "source_review",
                "processing_status": status,
            }
        )
    entities = [dict(entity_id=qid, type="LOC") for qid in ("Q1", "Q6", "PROV_x")]
    links = [
        dict(mention_id=current[i]["mention_id"], entity_id=qid, entity_type="LOC")
        for i, qid in ((0, "Q1"), (1, "PROV_x"), (4, "Q6"))
    ]
    save_core(core, current, links, entities)
    return previous, core, original, current, links, entities


def test_workflow_report_counts_all_rows_and_current_eligible_changes_separately(
    tmp_path,
):
    previous, core, *_ = inputs(tmp_path)
    output = tmp_path / "comparison"
    result = report.compare_workflows(previous, core, output)
    assert result["comparison_kind"] == "WORKFLOW_COMPARISON"
    assert result["original_rows"] == 6
    assert result["row_lineage_verified"] is True
    assert result["source_changed_rows"] == 6
    assert result["denominators"] == dict(
        all_original_rows=6,
        currently_eligible_rows=3,
        source_excluded_rows=1,
        source_review_rows=1,
        deferred_date_rows=1,
        date_type_rows=1,
        page_revision_unresolved_rows=0,
        pending_rows=0,
    )
    assert result["all_rows"]["lost_all_matches_rows"] == 2
    assert result["currently_eligible"]["lost_all_matches_rows"] == 1
    assert result["currently_eligible"]["newly_matched_rows"] == 1
    assert result["currently_eligible"]["changed_qid_rows"] == 1
    assert result["currently_eligible"]["new_row_qid_pairs"] == 2
    assert result["currently_eligible"]["lost_row_qid_pairs"] == 2
    assert result["noneligible_previous_matched_rows"] == 1
    assert result["accuracy"] is None and result["precision"] is None
    assert result["candidate_truth_status"] == result["model_truth_status"] == "UNKNOWN"
    cases = [
        json.loads(line)
        for line in (output / "workflow_rows.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(cases) == 6
    assert cases[1]["current_qids"] == []
    assert cases[4]["added_qids"] == ["Q6"] and cases[4]["removed_qids"] == ["Q5"]
    assert cases[2]["current_status"] == "SOURCE_EXCLUDED"
    assert (output / "workflow_rows.csv").is_file()
    with pytest.raises(FileExistsError):
        report.compare_workflows(previous, core, output)


@pytest.mark.parametrize(
    "corruption",
    [
        "row_missing",
        "duplicate_row",
        "raw_text",
        "raw_score",
        "raw_word",
        "revision",
        "unknown_endpoint",
        "wrong_type",
        "ineligible_link",
        "duplicate_link",
        "source_not_qid",
        "raw_source_conflict",
    ],
)
def test_workflow_report_rejects_unverified_lineage_or_broken_core(
    tmp_path, corruption
):
    previous, core, original, current, links, entities = inputs(tmp_path)
    if corruption == "row_missing":
        current.pop()
    elif corruption == "duplicate_row":
        current[-1]["source_row_index"] = 0
    elif corruption == "raw_text":
        current[0]["raw"]["Text"] = "changed"
    elif corruption == "raw_score":
        current[0]["raw"]["score"] = 0.9
    elif corruption == "raw_word":
        current[0]["raw"]["word"] = "Tokyo"
    elif corruption == "revision":
        current[0]["revision_id"] = 11
    elif corruption == "unknown_endpoint":
        links[0]["entity_id"] = "Q99"
    elif corruption == "wrong_type":
        links[0]["entity_type"] = "PER"
    elif corruption == "ineligible_link":
        current[0]["matching_eligible"] = False
    elif corruption == "duplicate_link":
        links.append(dict(links[0]))
    elif corruption == "source_not_qid":
        current[0]["Source"] = current[0]["raw"]["Source"] = "Tokyo page"
    elif corruption == "raw_source_conflict":
        current[0]["raw"]["Source"] = "Q17"
    save_core(core, current, links, entities)
    with pytest.raises(ValueError):
        report.compare_workflows(previous, core, tmp_path / "comparison")
    assert not (tmp_path / "comparison").exists()


def test_corrected_export_uses_original_literal_for_lineage_not_repaired_word(tmp_path):
    previous, core, original, *_ = inputs(tmp_path)
    for old in original:
        old["word_original"], old["word"] = old["word"], "repaired working name"
    pq.write_table(
        pa.Table.from_pylist(original), previous / "matched_mentions.parquet"
    )
    result = report.compare_workflows(previous, core, tmp_path / "comparison")
    assert result["row_lineage_verified"] is True


def test_workflow_report_rejects_changed_core_bytes_after_manifest(tmp_path):
    previous, core, *_ = inputs(tmp_path)
    with gzip.open(core / "entities.json.gz", "wt", encoding="utf-8") as stream:
        json.dump([], stream)
    with pytest.raises(ValueError, match="hash|binding"):
        report.compare_workflows(previous, core, tmp_path / "comparison")


def test_workflow_report_retains_root_processing_stage_metadata(tmp_path):
    previous, core, *_ = inputs(tmp_path)
    manifest_path = core / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["processing_stage"] = manifest.pop("stage")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = report.compare_workflows(previous, core, tmp_path / "comparison")
    assert result["current_stage"] == "final"


def test_workflow_report_rejects_boolean_current_source_row_index(tmp_path):
    previous, core, _, current, links, entities = inputs(tmp_path)
    current[1]["source_row_index"] = True
    save_core(core, current, links, entities)
    with pytest.raises(ValueError, match="lineage"):
        report.compare_workflows(previous, core, tmp_path / "comparison")

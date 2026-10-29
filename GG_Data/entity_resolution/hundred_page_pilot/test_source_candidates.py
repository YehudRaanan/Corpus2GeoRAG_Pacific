"""Source evidence protects retrieval, without becoming automatic identity proof."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
    exact_pairs,
    group_mentions,
    prepare,
)


def row(index, word, **extra):
    return dict(
        page_id=1,
        revision_id=11,
        source_row_index=index,
        word=word,
        entity_group="PER",
        Text="x" * 300 + word,
        start=300,
        end=300 + len(word),
        **extra
    )


def test_repaired_groups_keep_original_context_and_cannot_exact_match():
    rows = [
        row(
            0,
            "Complete Name",
            word_original="Name",
            repair_status="repaired",
            repair_qid_guided=True,
            source_candidate_qids=["Q9"],
        ),
        row(
            1,
            "Complete Name",
            word_original="Complete Name",
            repair_status="unchanged",
            repair_qid_guided=False,
            source_candidate_qids=["Q8"],
        ),
    ]
    groups = group_mentions(rows)
    assert groups[0]["source_candidate_qids"] == ["Q8", "Q9"]
    assert groups[0]["repaired_source_row_indices"] == [0]
    assert groups[0]["context"] == rows[0]["Text"][140:]
    entities = [dict(page_id=1, revision_id=11, qid="Q9", label="Complete Name")]
    assert not exact_pairs(groups, entities)


def test_unchanged_original_literal_keeps_independent_exact_proof():
    groups = group_mentions(
        [
            row(
                0,
                "Complete Name",
                word_original="Complete Name",
                repair_status="source_supported_unchanged",
                repair_qid_guided=True,
                source_candidate_qids=["Q9"],
            )
        ]
    )
    entities = [dict(page_id=1, revision_id=11, qid="Q9", label="Complete Name")]
    assert len(exact_pairs(groups, entities)) == 1
    assert not exact_pairs(groups, [*entities, {**entities[0], "qid": "Q8"}])
    changed = group_mentions(
        [
            row(
                0,
                "Complete Name",
                word_original="Name",
                repair_status="repaired",
                repair_qid_guided=True,
            )
        ]
    )
    assert not exact_pairs(changed, entities)


def test_source_candidates_are_union_with_top_k_and_date_exclusion_is_explicit(
    tmp_path,
):
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    rows = [
        row(0, "Target Person", source_candidate_qids=[]),
        row(1, "Zzz", source_candidate_qids=["Q1"]),
        {**row(2, "1942"), "entity_group": "DATE"},
    ]
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    pq.write_table(
        pa.Table.from_pylist(
            [
                dict(
                    page_id=1,
                    revision_id=11,
                    qid="Q1",
                    label="Target",
                    aliases=[],
                    description="",
                )
            ]
        ),
        entities,
    )
    output = tmp_path / "matching"
    summary = prepare(mentions, entities, output, 1, exclude_date=True)
    job = json.loads((output / "jobs.jsonl").read_text())
    assert {c["name"] for c in job["candidates"]} == {"Target Person", "Zzz"}
    assert job["protected_candidate_count"] == 1
    assert job["protected_candidates_added"] == 1
    assert summary["excluded_date_rows"] == 1
    assert summary["candidate_union_pairs_including_stop"] == 3
    assert len(group_mentions(rows)) == 3
    assert len(group_mentions(rows, exclude_date=True)) == 2


@pytest.mark.parametrize(
    "status",
    [
        "source_target_review",
        "source_context_review",
        "source_type_review",
        "ambiguous_surface",
        "partial_source_overlap",
        "invalid_original_offsets",
    ],
)
def test_review_status_blocks_exact_without_changing_legacy_groups(status):
    entities = [dict(page_id=1, revision_id=11, qid="Q9", label="Name")]
    legacy = group_mentions([row(0, "Name")])
    reviewed = group_mentions([row(0, "Name", repair_status=status)])
    assert len(exact_pairs(legacy, entities)) == 1
    assert reviewed[0]["source_review_statuses"] == [status]
    assert not exact_pairs(reviewed, entities)


def scoped_row(index, word, status="KEEP", **extra):
    return row(
        index,
        word,
        source_scope_status=status,
        source_scope_policy_version="article-source-v1",
        source_scope_context="clean context",
        **extra
    )


def test_source_gate_precedes_type_qid_repair_and_context_aggregation():
    rows = [
        scoped_row(0, "Japan"),
        {
            **scoped_row(
                1,
                "Japan",
                "EXCLUDE",
                source_candidate_qids=["Q999"],
                repair_status="repaired",
            ),
            "entity_group": "ORG",
        },
        scoped_row(2, "Japan", "REVIEW", source_candidate_qids=["Q998"]),
    ]
    groups = group_mentions(rows)
    assert len(groups) == 1
    assert groups[0]["source_row_indices"] == [0]
    assert groups[0]["context"] == "clean context"
    assert groups[0]["source_candidate_qids"] == []
    assert groups[0]["repaired_source_row_indices"] == []
    assert (
        len(
            exact_pairs(
                groups, [dict(page_id=1, revision_id=11, qid="Q17", label="Japan")]
            )
        )
        == 1
    )


@pytest.mark.parametrize(
    "change",
    [
        {"source_scope_status": None},
        {"source_scope_status": "OTHER"},
        {"source_scope_policy_version": "unknown"},
        {"source_scope_context": None},
    ],
)
def test_invalid_scope_annotations_fail_closed(change):
    with pytest.raises(ValueError, match="source-scope"):
        group_mentions([{**scoped_row(0, "Japan"), **change}])


def test_mixed_or_bypassed_scope_annotations_are_rejected():
    with pytest.raises(ValueError, match="source-scope"):
        group_mentions([scoped_row(0, "Japan"), row(1, "Japan")])
    with pytest.raises(ValueError, match="source policy"):
        group_mentions([scoped_row(0, "Japan")], source_policy="LEGACY_UNFILTERED")

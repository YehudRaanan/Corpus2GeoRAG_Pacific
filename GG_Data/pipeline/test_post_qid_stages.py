"""Stage writes preserve audit rows without creating premature graph identities."""

import copy
import gzip
import json

import pytest

from GG_Data.pipeline import post_qid_entities as entities
from GG_Data.pipeline import post_qid_mentions as mentions

HASH = "a" * 64


def row(index=0, **changes):
    value = dict(
        source_row_index=index,
        page_id=1,
        revision_id=10,
        revision_status="VERIFIED_RAW_CONTENT",
        word="Tokyo",
        word_original="[[Tokyo]]",
        raw_original_word="[[Tokyo]]",
        entity_group="LOC",
        Text="[[Tokyo]]",
        start=0,
        end=9,
        score=0.8,
        Source="Q1490",
        Index="paragraph 1",
        subtype=None,
        Text_clean="Tokyo",
        clean_start=0,
        clean_end=5,
        clean_status="mapped",
        clean_source_status="unique_raw_placement",
        clean_reason="exact_source_coverage",
        clean_policy_version="source-text-v3",
        matching_eligible=True,
        clean_revision_sha256="d" * 64,
        matching_eligibility_reason="eligible",
    )
    value.update(changes)
    return value


def group(index=0, gid="g", **changes):
    value = dict(
        id=gid,
        page_id=1,
        revision_id=10,
        name="Tokyo",
        type="LOC",
        source_row_indices=[index],
    )
    value.update(changes)
    return value


def mention_rows(rows, groups=(), pairs=(), stage="pending", **kwargs):
    return mentions.populate(
        list(rows),
        list(groups),
        list(pairs),
        input_sha256=HASH,
        dataset_namespace="new-input",
        stage=stage,
        **kwargs,
    )


def entity_rows(
    groups=(), pairs=(), stage="pending", eligible_group_ids=None, **kwargs
):
    return entities.populate(
        list(groups),
        list(pairs),
        input_sha256=HASH,
        dataset_namespace="new-input",
        stage=stage,
        eligible_group_ids=eligible_group_ids,
        **kwargs,
    )


def test_pending_preserves_raw_and_working_values_without_identity():
    source = row()
    before = copy.deepcopy(source)
    result = mention_rows([source])
    saved = result["mentions"][0]
    assert source == before
    assert result["mention_entity_links"] == []
    assert saved["processing_status"] == "PENDING_MATCHING"
    assert saved["raw"] == dict(
        entity_group="LOC",
        score=0.8,
        word="[[Tokyo]]",
        start=0,
        end=9,
        Source="Q1490",
        Index="paragraph 1",
        Text="[[Tokyo]]",
        subtype=None,
    )
    assert (
        saved["word"]
        == saved["Text_clean"][saved["clean_start"] : saved["clean_end"]]
        == "Tokyo"
    )
    assert saved["word_original"] == "[[Tokyo]]"
    assert saved["Source"] == "Q1490" and saved["wiki_page_id"] == 1
    assert saved["mention_id"] == saved["occurrence_id"]
    assert entity_rows() == []


@pytest.mark.parametrize(
    "changes,status",
    [
        (
            {"page_id": None, "revision_id": None, "matching_eligible": False},
            "PAGE_REVISION_UNRESOLVED",
        ),
        ({"revision_id": None, "matching_eligible": False}, "PAGE_REVISION_UNRESOLVED"),
        (
            {
                "clean_status": "excluded",
                "clean_start": None,
                "clean_end": None,
                "matching_eligible": False,
                "matching_eligibility_reason": "source_span_removed",
            },
            "SOURCE_EXCLUDED",
        ),
        (
            {
                "clean_status": "uncertain",
                "matching_eligible": False,
                "matching_eligibility_reason": "source_review_overlap",
            },
            "SOURCE_REVIEW",
        ),
        (
            {
                "entity_group": "DATE",
                "matching_eligible": False,
                "matching_eligibility_reason": "deferred_date",
            },
            "DEFERRED_DATE",
        ),
    ],
)
def test_ineligible_audit_rows_remain_without_groups_or_links(changes, status):
    result = mention_rows([row(**changes)], stage="final")
    assert len(result["mentions"]) == 1
    assert result["mentions"][0]["processing_status"] == status
    assert result["mention_entity_links"] == []


def test_stage_closure_only_adds_provisional_for_eligible_unmatched_groups():
    rows = [row(), row(1, entity_group="ORG")]
    groups = [group(), group(1, "h", type="ORG")]
    pairs = [dict(group_id="g", qid=q, method="exact") for q in ("Q1", "Q2")]
    early = mention_rows(rows, groups, pairs, "exact")
    final = mention_rows(rows, groups, pairs, "final")
    assert [r["mention_id"] for r in early["mentions"]] == [
        r["mention_id"] for r in final["mentions"]
    ]
    assert [r["processing_status"] for r in early["mentions"]] == [
        "ACCEPTED_EXACT",
        "PENDING_MATCHING",
    ]
    assert [r["processing_status"] for r in final["mentions"]] == [
        "ACCEPTED_EXACT",
        "ENTITY_UNRESOLVED",
    ]
    assert len(early["mention_entity_links"]) == 2
    assert len(final["mention_entity_links"]) == 3
    early_entities = entity_rows(groups, pairs, "exact", {"g", "h"})
    final_entities = entity_rows(groups, pairs, "final", {"g", "h"})
    assert {(e["entity_id"], e["type"]) for e in early_entities} == {
        ("Q1", "LOC"),
        ("Q2", "LOC"),
    }
    endpoints = {(e["entity_id"], e["type"]) for e in final_entities}
    assert len(endpoints) == 3
    assert all(
        (p["entity_id"], p["entity_type"]) in endpoints
        for p in final["mention_entity_links"]
    )


def test_raw_input_word_is_separate_from_earliest_word_original():
    saved = mention_rows(
        [row(word_original="older broken spelling", raw_original_word="[[Tokyo]]")]
    )["mentions"][0]
    assert saved["raw"]["word"] == "[[Tokyo]]"
    assert saved["word_original"] == "older broken spelling"


def test_supplied_occurrence_identity_cannot_change_with_stage_or_input():
    saved = mention_rows([row()])["mentions"][0]
    with pytest.raises(ValueError, match="identity|mention fields"):
        mention_rows([row(occurrence_id=saved["occurrence_id"], input_sha256="b" * 64)])
    with pytest.raises(ValueError, match="identity|mention fields"):
        mention_rows([row(occurrence_id="another occurrence")])


@pytest.mark.parametrize(
    "stage,finalize",
    [("pending", True), ("exact", True), ("final", False), ("unknown", None)],
)
def test_invalid_stage_closure_is_rejected(stage, finalize):
    with pytest.raises(ValueError, match="stage|final"):
        mention_rows([row()], stage=stage, finalize=finalize)


def test_ineligible_groups_cannot_create_accepted_entities_or_links():
    pair = dict(group_id="g", qid="Q1", method="exact")
    with pytest.raises(ValueError, match="eligible"):
        mention_rows(
            [
                row(
                    matching_eligible=False,
                    matching_eligibility_reason="source_context_review",
                )
            ],
            [group()],
            [pair],
            "final",
        )
    with pytest.raises(ValueError, match="eligible"):
        entity_rows([group()], [pair], "final", set())
    assert entity_rows([group()], [], "final", set()) == []
    with pytest.raises(ValueError, match="eligible"):
        entity_rows([group(type="DATE")], [pair], "final", {"g"})


def test_final_requires_eligible_group_coverage_but_pending_does_not():
    assert len(mention_rows([row()])["mentions"]) == 1
    with pytest.raises(ValueError, match="group"):
        mention_rows([row()], stage="final")


def test_model_phase_requires_accepted_pair_provenance_in_both_tables():
    pair = dict(group_id="g", qid="Q1", method="model")
    for call in (
        lambda: mention_rows([row()], [group()], [pair], "model"),
        lambda: entity_rows([group()], [pair], "model", {"g"}),
    ):
        with pytest.raises(ValueError, match="provenance"):
            call()


@pytest.mark.parametrize(
    "changes",
    [
        {"clean_status": "uncertain"},
        {"clean_source_status": "nonunique_raw_placement"},
        {"clean_end": 4},
        {"clean_revision_sha256": None},
        {"revision_status": "FAILED_RAW_CONTENT"},
    ],
)
def test_true_eligibility_cannot_bypass_saved_clean_or_revision_evidence(changes):
    with pytest.raises(ValueError, match="eligib"):
        mention_rows([row(**changes)], [group()], stage="final")


def test_failed_revision_with_nonnull_ids_is_page_failure_not_source_review():
    result = mention_rows(
        [
            row(
                revision_status="FAILED_RAW_CONTENT",
                matching_eligible=False,
                matching_eligibility_reason="page_revision_unresolved",
            )
        ],
        stage="final",
    )
    assert result["mentions"][0]["processing_status"] == "PAGE_REVISION_UNRESOLVED"
    assert result["mention_entity_links"] == []


def test_source_review_date_retains_source_reason_before_date_deferral():
    result = mention_rows(
        [
            row(
                entity_group="DATE",
                clean_status="uncertain",
                matching_eligible=False,
                matching_eligibility_reason="source_review",
            )
        ],
        stage="final",
    )
    assert result["mentions"][0]["processing_status"] == "SOURCE_REVIEW"


def test_pending_file_write_keeps_null_ids_and_binds_stage(tmp_path):
    source, groups, pairs = (
        tmp_path / name for name in ("rows.json", "groups.jsonl", "pairs.json")
    )
    source.write_text(
        json.dumps([row(page_id=None, revision_id=None, matching_eligible=False)]),
        encoding="utf-8",
    )
    groups.write_text("", encoding="utf-8")
    pairs.write_text("[]", encoding="utf-8")
    target = tmp_path / "pending"
    manifest = mentions.run(
        source,
        groups,
        pairs,
        target,
        input_sha256=HASH,
        dataset_namespace="new-input",
        stage="pending",
    )
    assert manifest["stage"] == "pending" and manifest["finalized"] is False
    assert manifest["page_ids"] == []
    assert manifest["counts"] == {"mentions": 1, "mention_entity_links": 0}
    with gzip.open(target / "mentions.json.gz", "rt", encoding="utf-8") as stream:
        assert json.load(stream)[0]["processing_status"] == "PAGE_REVISION_UNRESOLVED"
    with pytest.raises(FileExistsError):
        mentions.run(
            source,
            groups,
            pairs,
            target,
            input_sha256=HASH,
            dataset_namespace="new-input",
            stage="pending",
        )


def test_entity_file_subset_filters_explicit_eligibility_and_rejects_unknown_pairs(
    tmp_path,
):
    groups, pairs = tmp_path / "groups.jsonl", tmp_path / "pairs.json"
    gs = [group(), group(1, "h", page_id=2, revision_id=20)]
    groups.write_text("\n".join(map(json.dumps, gs)), encoding="utf-8")
    pairs.write_text("[]", encoding="utf-8")
    manifest = entities.run(
        groups,
        pairs,
        tmp_path / "final",
        input_sha256=HASH,
        dataset_namespace="new-input",
        stage="final",
        page_ids={1},
        eligible_group_ids={"g", "h"},
    )
    assert manifest["finalized"] is True and manifest["row_count"] == 1
    pairs.write_text(
        json.dumps([dict(group_id="missing", qid="Q1", method="exact")]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="group"):
        entities.run(
            groups,
            pairs,
            tmp_path / "bad",
            input_sha256=HASH,
            dataset_namespace="new-input",
            stage="final",
            page_ids={1},
            eligible_group_ids={"g", "h"},
        )
    assert not (tmp_path / "bad").exists()

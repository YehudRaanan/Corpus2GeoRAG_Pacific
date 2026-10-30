"""Filtered QID scope must apply before exact acceptance and candidate ranking."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot import match_exact, prepare_candidates


def inventory(**changes):
    return (
        dict(
            page_id=1,
            revision_id=11,
            qid="Q17",
            label="Japan",
            type_categories=["LOC"],
            type_unknown=False,
            qid_source_status="KEEP",
            qid_filter_policy_version="fixture",
        )
        | changes
    )


def mention(index=0, **changes):
    return (
        dict(
            source_row_index=index,
            page_id=1,
            revision_id=11,
            word="Japan",
            entity_group="LOC",
            Text="Japan",
            start=0,
            end=5,
        )
        | changes
    )


@pytest.mark.parametrize(
    "changes", [dict(type_categories=["PER"]), dict(qid_source_status="EXCLUDE")]
)
def test_exact_rejects_incompatible_or_source_excluded_qid(changes):
    groups = prepare_candidates.group_mentions([mention()])
    assert match_exact.exact_pairs(groups, [inventory(**changes)]) == []


def test_exact_uniqueness_uses_source_scope_before_type_compatibility():
    groups = prepare_candidates.group_mentions([mention()])
    allowed = inventory()
    excluded = inventory(qid="Q99", qid_source_status="EXCLUDE")
    assert [p["qid"] for p in match_exact.exact_pairs(groups, [allowed, excluded])] == [
        "Q17"
    ]
    # Type incompatibility must not convert two retained literal QIDs to one.
    assert not match_exact.exact_pairs(
        groups, [allowed, inventory(qid="Q99", type_categories=["PER"])]
    )


@pytest.mark.parametrize(
    "changes,wanted",
    [
        (dict(), {"LOC", "MISC"}),
        (
            dict(
                type_categories=[], type_unknown=True, qid_source_status="UNKNOWN_KEEP"
            ),
            {"PER", "LOC", "MISC"},
        ),
        (dict(qid_source_status="REVIEW"), {"LOC", "MISC"}),
        (dict(qid_source_status="EXCLUDE"), set()),
    ],
)
@pytest.mark.parametrize("protected", [True, False])
def test_candidates_filter_before_ranking_protection_and_review_coverage(
    tmp_path, changes, wanted, protected
):
    # PER is the highest literal score and is protected by source evidence.
    # Every group requires review, so coverage must not restore forbidden pairs.
    rows = [
        mention(
            i,
            entity_group=typ,
            word=word,
            repair_status="source_target_review",
            source_candidate_qids=["Q17"] if protected else [],
        )
        for i, (typ, word) in enumerate(
            [
                ("PER", "Japan"),
                ("LOC", "Japanese"),
                ("MISC", "Country"),
                ("DATE", "1945"),
            ]
        )
    ]
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    pq.write_table(pa.Table.from_pylist([inventory(**changes)]), entities)
    output = tmp_path / "matching"
    summary = prepare_candidates.prepare(mentions, entities, output, 1)
    jobs = [
        json.loads(line) for line in (output / "jobs.jsonl").read_text().splitlines()
    ]
    candidates = [candidate for job in jobs for candidate in job["candidates"]]
    assert {candidate["type"] for candidate in candidates} == wanted
    if wanted:
        assert jobs[0]["total_local_candidates"] == len(wanted)
        assert jobs[0]["top_trigram_candidate_count"] == 1
        assert candidates[0]["type"] == ("PER" if "PER" in wanted else "LOC")
    else:
        assert jobs == []
    assert len(summary["review_group_coverage"]["no_inventory_groups"]) == 4 - len(
        wanted
    )


def test_model_name_fallback_ranks_without_becoming_an_exact_label(tmp_path):
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist([mention()]), mentions)
    pq.write_table(
        pa.Table.from_pylist(
            [inventory(label=None, model_name="Japan", model_aliases=["Nippon"])]
        ),
        entities,
    )
    output = tmp_path / "matching"
    summary = prepare_candidates.prepare(mentions, entities, output, 1)
    assert summary["exact_pairs"] == 0
    assert summary["missing_entity_names"] == 0
    job = json.loads((output / "jobs.jsonl").read_text())
    assert job["entity"]["name"] == "Japan"
    assert job["entity"]["aliases"] == ["Nippon"]
    assert job["candidates"][0]["trigram"] == 1.0

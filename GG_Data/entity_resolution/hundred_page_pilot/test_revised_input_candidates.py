"""New-input lineage and clean-view matching contracts, with local evidence only."""

import gzip
import hashlib
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot import (
    prepare_candidates,
    prepare_pages,
)


def source_row(index=0, **changes):
    row = dict(
        entity_group="LOC",
        score=0.9,
        word="Japan",
        start=2,
        end=7,
        Source="Japan article",
        Index=index,
        Text="[[Japan]]",
        subtype="LOC",
    )
    return row | changes


def frozen_fixture(tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    (old / "selection.json").write_text(
        json.dumps(dict(input_sha256="a" * 64, source_titles=["Japan article"])),
        encoding="utf-8",
    )
    rows = [source_row(0), source_row(1, Source="Other article"), source_row(2)]
    new = tmp_path / "new.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [r | {"Source": "Q17" if i != 1 else "Q99"} for i, r in enumerate(rows)]
        ),
        new,
    )
    selected = [
        rows[i]
        | dict(
            source_row_index=i,
            page_id=1,
            revision_id=11,
            revision_status="VERIFIED_RAW_CONTENT",
            passage_id=f"p{i}",
        )
        for i in (0, 2)
    ]
    pq.write_table(pa.Table.from_pylist(selected), old / "selected_mentions.parquet")
    raw = old / "raw.txt"
    raw.write_bytes(b"[[Japan]]")
    evidence = old / "evidence.json.gz"
    response = dict(
        parse=dict(pageid=1, revid=11, title="Japan article", wikitext="[[Japan]]")
    )
    with gzip.open(evidence, "wt", encoding="utf-8") as stream:
        json.dump(dict(ok=True, response_text=json.dumps(response)), stream)
    revision = dict(
        page_id=1,
        revision_id=11,
        wikitext_path=str(raw),
        sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        evidence_path=str(evidence),
    )
    pq.write_table(pa.Table.from_pylist([revision]), old / "revisions.parquet")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            dict(
                input_sha256=hashlib.sha256(new.read_bytes()).hexdigest(),
                non_Source_columns_identical_all_rows=True,
                saved_sample_all_non_Source_values_identical=True,
                rows=3,
                saved_sample_rows=2,
                saved_sample_pages=1,
                saved_sample_revisions=1,
                sample_title_to_new_source={"Japan article": "Q17"},
            )
        ),
        encoding="utf-8",
    )
    return old, new, receipt


def test_adapter_uses_frozen_global_indices_and_keeps_new_source(tmp_path):
    old, new, receipt = frozen_fixture(tmp_path)
    output = tmp_path / "adapted"
    assert hasattr(
        prepare_pages, "adapt_frozen_input"
    ), "new QID input needs a frozen-row adapter"
    summary = prepare_pages.adapt_frozen_input(new, old, output, receipt)
    rows = pq.read_table(output / "selected_mentions.parquet").to_pylist()
    assert [r["source_row_index"] for r in rows] == [0, 2]
    assert [r["Source"] for r in rows] == ["Q17", "Q17"]
    assert all(
        r["source_title"] == "Japan article" and r["source_page_qid"] == "Q17"
        for r in rows
    )
    assert rows[0]["Text"] == "[[Japan]]" and rows[0]["start"] == 2
    assert rows[0]["raw_original_word"] == "Japan"
    assert rows[0]["occurrence_id"] != rows[1]["occurrence_id"]
    from GG_Data.pipeline.post_qid_entities import mention_id

    assert rows[0]["occurrence_id"] == mention_id(summary["input_sha256"], 0)
    assert len(pq.read_table(output / "selected_mentions.parquet").column_names) == len(
        set(rows[0])
    )
    assert summary["rows"] == 2 and summary["revisions"] == 1
    selection = json.loads((output / "selection.json").read_text())
    assert selection["input_sha256"] == summary["input_sha256"]
    assert (output / "frozen_selection.json").read_bytes() == (
        old / "selection.json"
    ).read_bytes()


@pytest.mark.parametrize("damage", ["word", "revision", "duplicate_metadata"])
def test_adapter_rejects_changed_lineage_or_revision_evidence(tmp_path, damage):
    old, new, receipt = frozen_fixture(tmp_path)
    assert hasattr(
        prepare_pages, "adapt_frozen_input"
    ), "adapter must validate reuse evidence"
    if damage == "word":
        table = pq.read_table(old / "selected_mentions.parquet").to_pylist()
        table[0]["word"] = "China"
        pq.write_table(pa.Table.from_pylist(table), old / "selected_mentions.parquet")
    elif damage == "revision":
        (old / "raw.txt").write_text("wrong", encoding="utf-8")
    else:
        table = pq.read_table(new)
        pq.write_table(
            table.append_column("source_row_index", pa.array([0, 1, 2])), new
        )
        record = json.loads(receipt.read_text())
        record["input_sha256"] = hashlib.sha256(new.read_bytes()).hexdigest()
        receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        prepare_pages.adapt_frozen_input(new, old, tmp_path / "adapted", receipt)


def clean_row(index=0, **changes):
    return (
        source_row()
        | dict(
            source_row_index=index,
            page_id=1,
            revision_id=11,
            revision_status="VERIFIED_RAW_CONTENT",
            word_original="Japan",
            Text_clean="Japan",
            clean_start=0,
            clean_end=5,
            clean_status="mapped",
            clean_source_status="unique_raw_placement",
            clean_revision_sha256="verified-hash",
            clean_policy_version="source-text-v3",
        )
        | changes
    )


def test_clean_groups_use_clean_context_and_immutable_occurrences():
    rows = [clean_row(occurrence_id="original-0")]
    groups = prepare_candidates.group_mentions(rows, exclude_date=True)
    assert groups[0]["context"] == "Japan", "model context must use the clean text"
    assert groups[0]["occurrence_ids"] == ["original-0"]
    assert rows[0]["Text"] == "[[Japan]]" and rows[0]["start"] == 2


@pytest.mark.parametrize(
    "changes",
    [
        dict(clean_status="excluded"),
        dict(page_id=None),
        dict(revision_id=None),
        dict(entity_group="DATE"),
    ],
)
def test_clean_candidate_groups_reject_ineligible_occurrences(changes):
    assert (
        prepare_candidates.group_mentions([clean_row(**changes)], exclude_date=True)
        == []
    )


def test_exact_stage_is_separate_and_reused_by_candidate_preparation(tmp_path):
    from importlib.util import find_spec

    assert find_spec(
        "GG_Data.entity_resolution.hundred_page_pilot.match_exact"
    ), "missing exact stage"
    from GG_Data.entity_resolution.hundred_page_pilot import match_exact

    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist([clean_row()]), mentions)
    pq.write_table(
        pa.Table.from_pylist(
            [dict(page_id=1, revision_id=11, qid="Q17", label="Japan")]
        ),
        entities,
    )
    exact = tmp_path / "exact"
    result = match_exact.prepare(mentions, entities, exact)
    assert result["exact_pairs"] == 1
    matching = tmp_path / "matching"
    result = prepare_candidates.prepare(
        mentions,
        entities,
        matching,
        1,
        exclude_date=True,
        exact_path=exact / "exact_pairs.parquet",
    )
    assert result["exact_pairs"] == 1
    jobs = [
        json.loads(line) for line in (matching / "jobs.jsonl").read_text().splitlines()
    ]
    assert jobs[0]["candidates"] == []


def test_exact_rule_stays_bilateral_literal_revision_local_and_repair_safe():
    from importlib.util import find_spec

    assert find_spec(
        "GG_Data.entity_resolution.hundred_page_pilot.match_exact"
    ), "missing exact stage"
    from GG_Data.entity_resolution.hundred_page_pilot.match_exact import exact_pairs

    groups = prepare_candidates.group_mentions([clean_row()], exclude_date=True)
    entity = dict(page_id=1, revision_id=11, qid="Q17", label="Japan")
    assert len(exact_pairs(groups, [entity])) == 1
    assert not exact_pairs(groups, [entity, entity | {"qid": "Q999"}])
    assert not exact_pairs(groups, [entity | {"revision_id": 12}])
    assert not exact_pairs(groups, [entity | {"label": "japan"}])
    ambiguous = prepare_candidates.group_mentions(
        [clean_row(), clean_row(1, entity_group="MISC")]
    )
    assert not exact_pairs(ambiguous, [entity])
    repaired = prepare_candidates.group_mentions(
        [clean_row(word_original="Japa", repair_status="repaired")]
    )
    assert not exact_pairs(repaired, [entity])


def test_cleaner_exports_common_eligibility_without_changing_raw_values(tmp_path):
    from GG_Data.entity_resolution.hundred_page_pilot.clean_source_text import (
        clean_mentions,
    )

    old, new, receipt = frozen_fixture(tmp_path)
    adapter = tmp_path / "adapted"
    prepare_pages.adapt_frozen_input(new, old, adapter, receipt)
    output = tmp_path / "clean"
    clean_mentions(
        adapter / "selected_mentions.parquet", adapter / "revisions.parquet", output
    )
    rows = pq.read_table(output / "mentions.parquet").to_pylist()
    assert (
        rows[0].get("matching_eligible") is True
    ), "cleaner must save the shared eligibility decision"
    assert rows[0]["matching_eligibility_reason"] == "eligible"
    assert rows[0]["Source"] == "Q17" and rows[0]["Text"] == "[[Japan]]"
    assert rows[0]["start"] == 2 and rows[0]["end"] == 7
    assert rows[0]["Text_clean"] == "Japan" and rows[0]["clean_start"] == 0
    assert (
        rows[0]["occurrence_id"]
        == pq.read_table(adapter / "selected_mentions.parquet")["occurrence_id"][
            0
        ].as_py()
    )


def test_mapped_span_with_context_review_enters_model_groups():
    row = clean_row(clean_text_needs_review=True)
    assert prepare_candidates.group_mentions([row], exclude_date=True)
    assert prepare_candidates.matching_eligibility(row) == (True, "eligible")


@pytest.mark.parametrize(
    "changes",
    [
        dict(clean_status="uncertain", clean_start=None, clean_end=None),
        dict(clean_source_status="nonunique_raw_placement"),
        dict(clean_end=4),
        dict(repair_status="source_target_review"),
    ],
)
def test_advisory_review_preserves_original_context_and_flags(changes):
    row = clean_row(**changes)
    before = dict(row)
    assert prepare_candidates.matching_eligibility(row) == (True, "eligible")
    context = prepare_candidates.matching_context(row)
    assert context is not None
    assert context["basis"] in {"clean", "original"}
    groups = prepare_candidates.group_mentions([row], exclude_date=True)
    assert groups[0]["review_source_row_indices"] == [0]
    assert groups[0]["context_sources"][0]["basis"] == context["basis"]
    assert row == before


def test_original_context_validates_original_word_after_repair():
    row = clean_row(
        word="Japanese Japan",
        raw_original_word="Japan",
        clean_status="uncertain",
        clean_start=None,
        clean_end=None,
        repair_status="repaired",
    )
    assert prepare_candidates.matching_context(row) == dict(
        text="[[Japan]]", start=2, end=7, basis="original"
    )
    assert prepare_candidates.matching_eligibility(row) == (True, "eligible")
    row["raw_original_word"] = "wrong"
    assert prepare_candidates.matching_context(row) is None
    assert prepare_candidates.matching_eligibility(row) == (False, "invalid_context")


def test_clean_removal_stays_excluded_before_review_and_date():
    row = clean_row(
        entity_group="DATE",
        clean_status="excluded",
        source_scope_status="REVIEW",
        source_scope_policy_version="article-source-v3",
        source_scope_context="uncertain source",
    )
    assert prepare_candidates.matching_eligibility(row, "article-source-v3") == (
        False,
        "source_excluded",
    )


@pytest.mark.parametrize("inventory", [True, False])
def test_review_group_coverage_protects_best_same_page_pair_or_reports_blocker(
    tmp_path, inventory
):
    rows = [
        clean_row(word="Japan", repair_status="source_target_review"),
        clean_row(1, word="Japon", repair_status="source_target_review"),
    ]
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    records = [dict(page_id=1, revision_id=11, qid="Q17", label="Japan country")]
    if not inventory:
        records[0]["revision_id"] = 12
    pq.write_table(pa.Table.from_pylist(records), entities)
    result = prepare_candidates.prepare(
        mentions, entities, tmp_path / "matching", 1, exclude_date=True
    )
    jobs = [
        json.loads(x)
        for x in (tmp_path / "matching/jobs.jsonl").read_text().splitlines()
    ]
    assert result["review_group_coverage"]["groups"] == 2
    if inventory:
        assert result["review_group_coverage"]["protected_pairs_added"] == 1
        assert len(jobs[0]["candidates"]) == 2
        assert result["review_group_coverage"]["no_inventory_groups"] == []
    else:
        assert len(result["review_group_coverage"]["no_inventory_groups"]) == 2
        assert not jobs[0]["candidates"]


def test_review_coverage_uses_highest_trigram_query_without_replacing_top_pool(
    tmp_path,
):
    rows = [
        clean_row(word="Alpha Bravo Charlie", repair_status="source_target_review"),
        clean_row(1, word="Omega", repair_status="source_target_review"),
    ]
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    pq.write_table(
        pa.Table.from_pylist(
            [
                dict(
                    page_id=1,
                    revision_id=11,
                    qid="Q17",
                    label="Alpha Bravo Charlie Omega",
                ),
                dict(
                    page_id=1,
                    revision_id=11,
                    qid="Q18",
                    label="Alpha Bravo Charlie Delta",
                ),
            ]
        ),
        entities,
    )
    result = prepare_candidates.prepare(
        mentions, entities, tmp_path / "matching", 1, exclude_date=True
    )
    assert result["matching_policy_version"] == "review-advisory-v1"
    assert result["review_group_coverage"]["protected_pairs_added"] == 1
    assert result["review_group_coverage"]["added_pairs"][0]["qid"] == "Q17"
    jobs = [
        json.loads(x)
        for x in (tmp_path / "matching/jobs.jsonl").read_text().splitlines()
    ]
    assert [{c["name"] for c in j["candidates"]} for j in jobs] == [
        {"Alpha Bravo Charlie", "Omega"},
        {"Alpha Bravo Charlie"},
    ]


def test_revised_source_review_is_advisory_but_raw_only_legacy_gate_is_preserved():
    row = clean_row(
        source_scope_status="REVIEW",
        source_scope_policy_version="article-source-v3",
        source_scope_context="original source evidence",
    )
    assert prepare_candidates.matching_eligibility(row, "article-source-v3") == (
        True,
        "eligible",
    )
    raw = {
        key: value
        for key, value in row.items()
        if not key.startswith("clean_") and key != "Text_clean"
    }
    assert prepare_candidates.matching_eligibility(raw, "article-source-v3") == (
        False,
        "source_review",
    )


def test_candidate_callable_preserves_existing_stage_outputs(tmp_path):
    mentions, entities = tmp_path / "mentions.parquet", tmp_path / "entities.parquet"
    pq.write_table(pa.Table.from_pylist([clean_row()]), mentions)
    pq.write_table(
        pa.Table.from_pylist(
            [dict(page_id=1, revision_id=11, qid="Q17", label="Japan")]
        ),
        entities,
    )
    output = tmp_path / "matching"
    prepare_candidates.prepare(mentions, entities, output, 80, exclude_date=True)
    jobs = (output / "jobs.jsonl").read_bytes()
    with pytest.raises(FileExistsError):
        prepare_candidates.prepare(mentions, entities, output, 80, exclude_date=True)
    assert (output / "jobs.jsonl").read_bytes() == jobs


@pytest.mark.parametrize(
    "repaired_end,want_status,want_word",
    [(7, "mapped", "Japan"), (6, "uncertain", "Japan")],
)
def test_cleaner_projects_only_exact_repaired_source_span(
    tmp_path, repaired_end, want_status, want_word
):
    from GG_Data.entity_resolution.hundred_page_pilot.clean_source_text import (
        clean_mentions,
    )

    old, _, _ = frozen_fixture(tmp_path)
    row = pq.read_table(old / "selected_mentions.parquet").to_pylist()[0]
    row |= dict(
        word="Japan",
        word_original="Jap",
        raw_original_word="Jap",
        start=2,
        end=5,
        repair_status="repaired",
        repaired_start=2,
        repaired_end=repaired_end,
        occurrence_id="immutable",
    )
    prepared = tmp_path / "prepared.parquet"
    pq.write_table(pa.Table.from_pylist([row]), prepared)
    output = tmp_path / "clean"
    clean_mentions(prepared, old / "revisions.parquet", output)
    result = pq.read_table(output / "mentions.parquet").to_pylist()[0]
    assert result["clean_status"] == want_status
    assert result["word"] == want_word
    assert (
        result["start"] == 2 and result["end"] == 5 and result["word_original"] == "Jap"
    )
    assert result["occurrence_id"] == "immutable"
    if want_status == "mapped":
        assert result["clean_start"] == 0 and result["clean_end"] == 5
        groups = prepare_candidates.group_mentions([result], exclude_date=True)
        assert groups[0]["name"] == "Japan"
        assert not prepare_candidates.exact_pairs(
            groups, [dict(page_id=1, revision_id=11, qid="Q17", label="Japan")]
        )

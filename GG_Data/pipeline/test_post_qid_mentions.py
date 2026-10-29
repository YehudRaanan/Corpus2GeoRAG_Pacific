"""Original-row preservation and typed many-to-many bridge regression cases."""

import copy
import gzip
import json

import pytest

from GG_Data.pipeline import post_qid_mentions as mentions
from GG_Data.pipeline.post_qid_entities import mention_id, provisional_id


def inputs():
    rows = [
        dict(
            source_row_index=i,
            page_id=page,
            revision_id=page * 10,
            word="May",
            entity_group="DATE",
            Text="May arrived.",
            start=0,
            end=3,
            score=0.8,
            Source=f"Page {page}",
            Index="paragraph 1",
            subtype=None,
        )
        for i, page in enumerate((1, 1, 2, 3))
    ]
    groups = [
        dict(
            id="a",
            page_id=1,
            revision_id=10,
            name="May",
            type="DATE",
            source_row_indices=[0, 1],
        ),
        dict(
            id="b",
            page_id=2,
            revision_id=20,
            name="May",
            type="DATE",
            source_row_indices=[2],
        ),
        dict(
            id="c",
            page_id=3,
            revision_id=30,
            name="May",
            type="DATE",
            source_row_indices=[3],
        ),
    ]
    pairs = [
        dict(
            group_id="a",
            qid=qid,
            method="model",
            page_id=1,
            revision_id=10,
            run_id="frozen-model",
            checkpoint_sha256="b" * 64,
            readiness_sha256="c" * 64,
            decision_reference={
                "path": "decisions.jsonl",
                "sha256": "d" * 64,
                "record_id": f"a:{qid}:0",
            },
        )
        for qid in ("Q1", "Q2")
    ]
    return rows, groups, pairs


def populate(rows, groups, pairs):
    return mentions.populate(
        rows, groups, pairs, input_sha256="a" * 64, dataset_namespace="frozen-100"
    )


def test_one_mention_can_link_to_more_than_two_qids():
    rows, groups, pairs = inputs()
    for qid in ("Q3", "Q4"):
        pair = copy.deepcopy(pairs[0])
        pair["qid"] = qid
        pair["decision_reference"]["record_id"] = f"a:{qid}:0"
        pairs.append(pair)
    result = populate(rows, groups, pairs)
    first = result["mentions"][0]["mention_id"]
    assert {
        link["entity_id"]
        for link in result["mention_entity_links"]
        if link["mention_id"] == first
    } == {"Q1", "Q2", "Q3", "Q4"}
    assert len(result["mentions"]) == len(rows)


def test_original_rows_many_to_many_and_global_unresolved_identity():
    rows, groups, pairs = inputs()
    original = copy.deepcopy((rows, groups, pairs))
    result = populate(rows, groups, pairs)
    assert (rows, groups, pairs) == original
    assert len(result["mentions"]) == 4
    assert len(result["mention_entity_links"]) == 6
    for source, row in zip(rows, result["mentions"]):
        assert row["raw"] == source
        assert all(row[key] == value for key, value in source.items())
        assert row["mention_id"] == mention_id("a" * 64, source["source_row_index"])
        assert (row["wiki_site"], row["wiki_page_id"], row["revision_id"]) == (
            "enwiki",
            source["page_id"],
            source["revision_id"],
        )
    links = result["mention_entity_links"]
    assert {link["entity_type"] for link in links} == {"DATE"}
    unresolved = [link for link in links if link["method"] == "unresolved"]
    assert len(unresolved) == 2
    assert {link["entity_id"] for link in unresolved} == {
        provisional_id("May", "DATE", "frozen-100")
    }
    assert links[0]["evidence"][0]["run_id"] == "frozen-model"


def test_duplicate_pair_dedups_bridge_but_keeps_distinct_evidence():
    rows, groups, pairs = inputs()
    pairs.extend(
        [dict(pairs[0]), {**pairs[0], "method": "exact", "run_id": "exact-audit"}]
    )
    result = populate(rows, groups, pairs)
    links = [
        link for link in result["mention_entity_links"] if link["entity_id"] == "Q1"
    ]
    assert len(links) == 2
    assert links[0]["methods"] == ["exact", "model"]
    assert len(links[0]["evidence"]) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", None),
        ("run_id", ""),
        ("checkpoint_sha256", "unbound"),
        ("readiness_sha256", None),
        ("decision_reference", "decisions.jsonl"),
        ("decision_reference", {}),
        ("decision_reference", {"path": "decisions.jsonl", "sha256": "d" * 64}),
        (
            "decision_reference",
            {"path": "decisions.jsonl", "sha256": "wrong", "record_id": "a:0"},
        ),
    ],
)
def test_model_pair_requires_run_checkpoint_readiness_and_decision_provenance(
    field, value
):
    rows, groups, pairs = inputs()
    pairs[0][field] = value
    with pytest.raises(ValueError, match="Model pair provenance"):
        populate(rows, groups, pairs)


def test_model_pair_cannot_mix_checkpoint_or_readiness_identity():
    rows, groups, pairs = inputs()
    pairs[1]["checkpoint_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="mix checkpoint/readiness"):
        populate(rows, groups, pairs)


def test_same_qid_keeps_different_daniel_types_and_provisional_namespace():
    rows, groups, pairs = inputs()
    rows[2]["entity_group"] = groups[1]["type"] = "PER"
    pairs.append(dict(group_id="b", qid="Q1", method="exact"))
    result = populate(rows, groups, pairs)
    assert {
        link["entity_type"]
        for link in result["mention_entity_links"]
        if link["entity_id"] == "Q1"
    } == {"DATE", "PER"}
    unresolved = next(
        link
        for link in result["mention_entity_links"]
        if link["method"] == "unresolved"
    )
    assert unresolved["entity_id"] != provisional_id("May", "DATE", "another-dataset")


@pytest.mark.parametrize(
    "corrupt",
    [
        "duplicate_row",
        "missing_group",
        "unknown_group_row",
        "duplicate_group_row",
        "literal",
        "type",
        "scope",
        "pair_scope",
        "pair_type",
        "unknown_pair",
        "bad_qid",
    ],
)
def test_corrupt_inputs_fail_without_dropping_rows(corrupt):
    rows, groups, pairs = inputs()
    if corrupt == "duplicate_row":
        rows.append(dict(rows[0]))
    elif corrupt == "missing_group":
        groups.pop()
    elif corrupt == "unknown_group_row":
        groups[0]["source_row_indices"].append(999)
    elif corrupt == "duplicate_group_row":
        groups[1]["source_row_indices"].append(0)
    elif corrupt == "literal":
        groups[0]["name"] = "may"
    elif corrupt == "type":
        groups[0]["type"] = "PER"
    elif corrupt == "scope":
        groups[0]["revision_id"] = 11
    elif corrupt == "pair_scope":
        pairs[0]["page_id"] = 9
    elif corrupt == "pair_type":
        pairs[0]["entity_group"] = "PER"
    elif corrupt == "unknown_pair":
        pairs[0]["group_id"] = "missing"
    elif corrupt == "bad_qid":
        pairs[0]["qid"] = "Q0"
    with pytest.raises(ValueError):
        populate(rows, groups, pairs)


def test_file_run_subset_jsonl_pairs_and_no_overwrite(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows, groups, pairs = inputs()
    source, group_path, pair_path = (
        tmp_path / name
        for name in ("selected_mentions.parquet", "groups.jsonl", "pairs.jsonl")
    )
    pq.write_table(pa.Table.from_pylist(rows), source)
    group_path.write_text("\n".join(map(json.dumps, groups)), encoding="utf-8")
    pair_path.write_text("\n".join(map(json.dumps, pairs)), encoding="utf-8")
    output = tmp_path / "stage"
    manifest = mentions.run(
        source,
        group_path,
        pair_path,
        output,
        input_sha256="a" * 64,
        dataset_namespace="frozen-100",
        page_ids={1, 2},
    )
    assert manifest["counts"] == {"mentions": 3, "mention_entity_links": 5}
    with gzip.open(output / "mentions.json.gz", "rt", encoding="utf-8") as stream:
        assert len(json.load(stream)) == 3
    with pytest.raises(FileExistsError):
        mentions.run(
            source,
            group_path,
            pair_path,
            output,
            input_sha256="a" * 64,
            dataset_namespace="frozen-100",
        )
    pair_path.write_text(json.dumps({**pairs[0], "revision_id": 999}), encoding="utf-8")
    with pytest.raises(ValueError):
        mentions.run(
            source,
            group_path,
            pair_path,
            tmp_path / "bad-stage",
            input_sha256="a" * 64,
            dataset_namespace="frozen-100",
        )
    assert not (tmp_path / "bad-stage").exists()

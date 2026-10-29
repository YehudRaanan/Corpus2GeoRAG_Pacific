import pytest

from GG_Data.pipeline import post_qid_entities as entities


def groups():
    return [
        dict(
            id="a",
            name="May",
            type="DATE",
            page_id=1,
            revision_id=10,
            source_row_indices=[1, 2],
        ),
        dict(
            id="b",
            name="May",
            type="DATE",
            page_id=2,
            revision_id=20,
            source_row_indices=[3],
        ),
        dict(
            id="c",
            name="May",
            type="PER",
            page_id=2,
            revision_id=20,
            source_row_indices=[4],
        ),
    ]


def test_many_to_many_and_unresolved_literal_identity_do_not_propagate():
    pairs = [dict(group_id="a", qid=q) for q in ("Q1", "Q2")]
    pairs.append(dict(group_id="c", qid="Q1"))
    rows = entities.populate(
        groups(), pairs, dataset_namespace="test", input_sha256="a" * 64
    )
    by_key = {(r["entity_id"], r["type"]): r for r in rows}
    assert (
        ("Q1", "DATE") in by_key
        and ("Q1", "PER") in by_key
        and ("Q2", "DATE") in by_key
    )
    unresolved = [r for r in rows if r["identity_status"] == "PROVISIONAL_UNRESOLVED"]
    assert len(unresolved) == 1 and unresolved[0]["type"] == "DATE"
    assert by_key["Q1", "DATE"]["attributes"]["mention_ids"] == [
        entities.mention_id("a" * 64, i) for i in (1, 2)
    ]
    assert by_key["Q1", "DATE"]["native_record_status"] == "MISSING"
    assert entities.provisional_id("May", "DATE", "test") != entities.provisional_id(
        "may", "DATE", "test"
    )
    assert entities.provisional_id("May", "DATE", "test") != entities.provisional_id(
        "May", "PER", "test"
    )


def test_full_native_record_preserved_and_p31_separate_from_daniel_type():
    full = dict(
        id="Q1",
        labels={"en": {"value": "Official"}},
        claims={"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q99"}}}}]},
        lastrevid=8,
    )
    rows = entities.populate(
        groups(),
        [dict(group_id="a", qid="Q1")],
        dataset_namespace="test",
        input_sha256="a" * 64,
        native_records={"Q1": dict(requested_qid="Q1", entity=full)},
        provenance={"Q1": {"provider": "FIXTURE"}},
    )
    row = next(r for r in rows if r["entity_id"] == "Q1")
    assert row["type"] == "DATE" and row["native_types"] == ["Q99"]
    assert row["raw_reference"]["full"]["entity"] == full and row["name"] == "Official"
    assert row["sources"] == [{"provider": "FIXTURE"}]


def test_shared_provisional_and_invalid_pair():
    rows = entities.populate(
        groups(), [], dataset_namespace="test", input_sha256="a" * 64
    )
    assert len(rows) == 2
    date = next(r for r in rows if r["type"] == "DATE")
    assert len(date["attributes"]["mention_ids"]) == 3
    with pytest.raises(ValueError):
        entities.populate(
            groups(),
            [dict(group_id="absent", qid="Q1")],
            dataset_namespace="test",
            input_sha256="a" * 64,
        )


def test_revision_mismatch_and_corrupt_native_record_stop():
    with pytest.raises(ValueError):
        entities.populate(
            groups(),
            [dict(group_id="a", qid="Q1", revision_id=11)],
            dataset_namespace="test",
            input_sha256="a" * 64,
        )
    with pytest.raises(ValueError):
        entities.populate(
            groups(),
            [dict(group_id="a", qid="Q1")],
            dataset_namespace="test",
            input_sha256="a" * 64,
            native_records={
                "Q1": dict(requested_qid="Q1", entity={"id": "Q2", "claims": {}})
            },
        )


def test_original_row_cannot_belong_to_conflicting_groups():
    bad = groups()
    bad[1]["source_row_indices"] = [1]
    with pytest.raises(ValueError):
        entities.populate(bad, [], dataset_namespace="test", input_sha256="a" * 64)


def test_missing_native_provenance_is_explicit_even_with_matching_metadata():
    row = next(
        r
        for r in entities.populate(
            groups(),
            [dict(group_id="a", qid="Q1")],
            dataset_namespace="test",
            input_sha256="a" * 64,
            metadata={"Q1": {"label": "May", "native_types": ["Q99"]}},
        )
        if r["entity_id"] == "Q1"
    )
    assert row["sources"] == [
        {
            "provider": "WIKIDATA",
            "record_id": "Q1",
            "status": "MISSING_FULL_NATIVE_RECORD",
        }
    ]
    assert row["native_types"] == []


def test_file_run_writes_readable_legacy_tables_without_overwriting(tmp_path):
    import gzip
    import json

    group_path, pairs = tmp_path / "groups.jsonl", tmp_path / "pairs.json"
    group_path.write_text("\n".join(json.dumps(g) for g in groups()), encoding="utf-8")
    pairs.write_text("[]", encoding="utf-8")
    output = tmp_path / "stage"
    manifest = entities.run(
        group_path,
        pairs,
        output,
        dataset_namespace="test",
        input_sha256="a" * 64,
        page_ids={1},
    )
    with gzip.open(output / "entities.json.gz", "rt", encoding="utf-8") as stream:
        rows = json.load(stream)
    assert manifest["row_count"] == len(rows) == 1
    assert rows[0]["attributes"]["source_page_ids"] == [1]
    with pytest.raises(FileExistsError):
        entities.run(
            group_path, pairs, output, dataset_namespace="test", input_sha256="a" * 64
        )


def test_supplied_null_native_is_corrupt_not_missing():
    with pytest.raises(ValueError, match="envelope"):
        entities.populate(
            groups(),
            [dict(group_id="a", qid="Q1")],
            dataset_namespace="test",
            input_sha256="a" * 64,
            native_records={"Q1": None},
        )


def test_qid_counts_shared_across_types_and_duplicate_pair_evidence():
    rows = entities.populate(
        groups(),
        [dict(group_id=g, qid="Q1") for g in ("a", "a", "c")],
        dataset_namespace="test",
        input_sha256="a" * 64,
    )
    for row in rows:
        if row["entity_id"] == "Q1":
            assert row["unique_original_mention_count"] == 3
            assert row["distinct_source_page_count"] == 2
            assert row["importance"] is None


def test_name_fallback_uses_whole_record_then_daniel_and_marks_ambiguity():
    gs = groups()
    gs[2]["name"] = "Different literal"
    pairs = [dict(group_id=g, qid="Q1") for g in ("a", "c")]
    rows = entities.populate(
        gs,
        pairs,
        dataset_namespace="test",
        input_sha256="a" * 64,
        metadata={"Q1": {"label": "Stale compact label"}},
    )
    qrows = [r for r in rows if r["entity_id"] == "Q1"]
    assert all(r["name"] is None for r in qrows)
    assert all(
        r["attributes"]["name_selection"]["status"] == "AMBIGUOUS_DANIEL_FALLBACK"
        for r in qrows
    )
    assert qrows[0]["attributes"]["name_selection"]["candidate_names"] == [
        "Different literal",
        "May",
    ]
    full = dict(id="Q1", claims={}, labels={"ja": {"value": "Native JA"}})
    rows = entities.populate(
        gs,
        pairs,
        dataset_namespace="test",
        input_sha256="a" * 64,
        native_records={"Q1": dict(requested_qid="Q1", entity=full)},
    )
    assert all(r["name"] == "Native JA" for r in rows if r["entity_id"] == "Q1")
    rows = entities.populate(
        groups(),
        [dict(group_id="a", qid="Q1")],
        dataset_namespace="test",
        input_sha256="a" * 64,
        metadata={"Q1": {"label": "Stale compact label"}},
    )
    assert next(r["name"] for r in rows if r["entity_id"] == "Q1") == "May"

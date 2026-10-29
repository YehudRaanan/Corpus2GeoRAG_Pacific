import pytest

from GG_Data.pipeline import post_qid_pages as pages


def test_used_revisions_and_subset_keep_revision_provenance():
    revisions = [
        dict(page_id=1, revision_id=r, wiki_title="A", sha256=str(r)) for r in (10, 11)
    ]
    revisions.append(dict(page_id=2, revision_id=20, wiki_title="B"))
    rows = pages.populate(revisions, page_ids={1})
    assert [(r["wiki_site"], r["wiki_page_id"], r["revision_id"]) for r in rows] == [
        ("enwiki", 1, 10),
        ("enwiki", 1, 11),
    ]
    assert rows[0]["content_sha256"] == "10"
    assert rows[0]["raw_reference"] == revisions[0]
    assert rows[0]["revision_url"] == "https://en.wikipedia.org/w/index.php?oldid=10"


def test_duplicate_or_missing_selected_revision_fails():
    row = dict(page_id=1, revision_id=10)
    with pytest.raises(ValueError):
        pages.populate([row, row])
    with pytest.raises(ValueError):
        pages.populate([row], page_ids={2})


def test_file_stage_checks_content_before_output(tmp_path):
    import hashlib

    import pyarrow as pa
    import pyarrow.parquet as pq

    text = tmp_path / "revision.txt"
    text.write_bytes(b"original content")
    row = dict(
        page_id=1,
        revision_id=10,
        wikitext_path=str(text),
        sha256=hashlib.sha256(b"original content").hexdigest(),
    )
    pq.write_table(pa.Table.from_pylist([row]), tmp_path / "revisions.parquet")
    manifest = pages.run(tmp_path, tmp_path / "stage")
    assert manifest["row_count"] == 1
    text.write_bytes(b"changed content")
    with pytest.raises(ValueError):
        pages.run(tmp_path, tmp_path / "changed-stage")
    assert not (tmp_path / "changed-stage").exists()


def test_supplied_page_qid_is_page_metadata_not_a_mention_assignment():
    rows = pages.populate([dict(page_id=1, revision_id=10)], page_qids={1: "Q42"})
    assert rows[0]["about_entity_id"] == "Q42"
    assert (
        rows[0]["about_entity_temporal_basis"]
        == "DANIEL_SUPPLIED_PAGE_QID_NOT_HISTORICAL_MAPPING_PROOF"
    )
    with pytest.raises(ValueError, match="QID"):
        pages.populate([dict(page_id=1, revision_id=10)], page_qids={1: "invalid"})

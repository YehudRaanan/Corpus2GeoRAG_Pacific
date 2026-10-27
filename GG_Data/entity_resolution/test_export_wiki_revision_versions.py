"""Check staged enrichment without changing accepted page IDs or raw values."""

import hashlib
import json

import export_wiki_revision_versions as subject
import pyarrow as pa
import pytest


def test_changed_saved_evidence_is_rejected_before_metadata_is_copied(tmp_path):
    evidence = tmp_path / "passage_decisions.jsonl.gz"
    evidence.write_bytes(b"accepted original evidence")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "files_sha256": {
                    evidence.name: hashlib.sha256(evidence.read_bytes()).hexdigest()
                }
            }
        )
    )
    subject.verify_saved_evidence(tmp_path)
    evidence.write_bytes(b"same page with different unaccepted revision")
    with pytest.raises(ValueError, match="evidence changed"):
        subject.verify_saved_evidence(tmp_path)


def test_history_only_updates_null_ids_then_metadata_backfills_without_matching():
    table = pa.table(
        {
            "Source": ["A", "B", "A"],
            "Text": ["Old", "New", "Old"],
            "wiki_page_id": pa.array([1, None, 1], type=pa.int64()),
        }
    ).replace_schema_metadata({b"raw": b"preserved"})
    decisions = {
        ("A", "Old"): {
            "wiki_page_id": 1,
            "revision_id": 10,
            "canonical_title": "A",
            "status": "VERIFIED_EXACT",
            "page_evidence": "pages/a.json.gz",
            "text_sha256": hashlib.sha256(b"Old").hexdigest(),
        },
        ("B", "New"): {
            "wiki_page_id": None,
            "status": "TEXT_NOT_FOUND",
            "text_sha256": hashlib.sha256(b"New").hexdigest(),
        },
    }
    historical = {
        ("B", "New"): {
            "pageid": 2,
            "revid": 20,
            "title": "B",
            "timestamp": "2025-01-01T00:00:00Z",
            "parse_evidence": "old.json.gz",
            "status": "VERIFIED_RENDERED",
        }
    }
    v1 = subject.enrich(table, decisions, historical)
    assert v1["wiki_page_id"].to_pylist() == [1, 2, 1]
    assert v1["wiki_revision_id"].to_pylist() == [None, 20, None]
    assert v1.select(["Source", "Text"]).equals(
        table.select(["Source", "Text"]), check_metadata=True
    )
    v2 = subject.enrich(
        table,
        decisions,
        historical,
        {
            10: {
                "pageid": 1,
                "revid": 10,
                "timestamp": "2026-01-01T00:00:00Z",
                "evidence": "meta.json.gz",
            }
        },
    )
    assert v2["wiki_page_id"].equals(v1["wiki_page_id"])
    assert v2["wiki_revision_id"].to_pylist() == [10, 20, 10]
    assert v2["wiki_match_method"].to_pylist() == [
        "VERIFIED_EXACT",
        "VERIFIED_RENDERED",
        "VERIFIED_EXACT",
    ]
    assert v2["wiki_revision_timestamp"].type == pa.timestamp("us", tz="UTC")
    assert v2.slice(1, 1).equals(v1.slice(1, 1), check_metadata=True)


def test_wrong_revision_page_and_overwriting_accepted_id_are_rejected():
    table = pa.table({"Source": ["A"], "Text": ["Old"], "wiki_page_id": [1]})
    decisions = {
        ("A", "Old"): {
            "wiki_page_id": 1,
            "revision_id": 10,
            "canonical_title": "A",
            "status": "VERIFIED_EXACT",
            "page_evidence": "x",
            "text_sha256": hashlib.sha256(b"Old").hexdigest(),
        }
    }
    with pytest.raises(ValueError, match="already assigned"):
        subject.enrich(table, decisions, {("A", "Old"): {"pageid": 2}})
    with pytest.raises(ValueError, match="revision/page"):
        subject.enrich(
            table,
            decisions,
            {},
            {10: {"pageid": 2, "revid": 10, "timestamp": "2026-01-01T00:00:00Z"}},
        )

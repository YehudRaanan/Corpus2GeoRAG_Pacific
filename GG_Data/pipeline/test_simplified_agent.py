"""Protect exact identities, full input lineage and directional page counts."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.pipeline import simplified_agent as subject
from GG_Data.pipeline.poc import digest, read_json


def input_file(tmp_path):
    keys = [
        ("A", "PER", "Q1"),
        ("A", "PER", "Q1"),
        ("A", "ORG", "Q1"),
        ("a", "PER", "Q2"),
        (" A", "PER", "Unresolved page"),
        ("1941", "DATE", "Q1"),
    ]
    rows = [
        dict(
            word=name,
            entity_group=kind,
            Source=page,
            score=0.8,
            start=0,
            end=len(name),
            Index=i,
            Text=name,
            subtype=kind,
        )
        for i, (name, kind, page) in enumerate(keys)
    ]
    path = tmp_path / "input.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path, rows


def test_prepare_keeps_exact_keys_and_every_raw_row(tmp_path):
    source, raw = input_file(tmp_path)
    out = tmp_path / "prepared"
    result = subject.prepare(source, out, expected_sha256=digest(source))
    entities = read_json(out / "entities.json.gz")
    mentions = read_json(out / "mentions.json.gz")
    assert {(r["name"], r["type"]) for r in entities} == {
        ("A", "PER"),
        ("A", "ORG"),
        ("a", "PER"),
        (" A", "PER"),
    }
    assert [r["raw"] for r in mentions] == raw
    assert [r["source_row_index"] for r in mentions] == list(range(6))
    assert mentions[-1]["entity_id"] is None
    assert mentions[-1]["exclusion_reason"] == "DATE_EXCLUDED"
    assert mentions[0]["entity_id"] == mentions[1]["entity_id"]
    assert mentions[0]["entity_id"] != mentions[2]["entity_id"]
    a = next(r for r in entities if (r["name"], r["type"]) == ("A", "PER"))
    assert a["mention_count"] == 2 and a["page_count"] == 1
    assert not any("qid" in r for r in entities)
    pages = read_json(out / "wiki_pages.json.gz")
    assert {r["source_key"] for r in pages} == {"Q1", "Q2", "Unresolved page"}
    assert all(r["wiki_page_id"] is None and r["revision_id"] is None for r in pages)
    assert result["counts"] == dict(
        raw_rows=6, excluded_date_rows=1, entities=4, pages=3, memberships=4
    )
    for name, sha in result["outputs"].items():
        assert digest(out / name) == sha
    assert json.loads((out / "manifest.json").read_text())["input"]["sha256"] == digest(
        source
    )


def test_prepare_rejects_wrong_hash_before_writing(tmp_path):
    source, _ = input_file(tmp_path)
    out = tmp_path / "prepared"
    with pytest.raises(ValueError, match="SHA256"):
        subject.prepare(source, out, expected_sha256="wrong")
    assert not out.exists()


def test_prepare_preserves_existing_output(tmp_path):
    source, _ = input_file(tmp_path)
    out = tmp_path / "prepared"
    out.mkdir()
    marker = out / "marker"
    marker.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        subject.prepare(source, out, expected_sha256=digest(source))
    assert marker.read_bytes() == b"keep"


def test_prepare_rejects_missing_identity(tmp_path):
    source, _ = input_file(tmp_path)
    table = pq.read_table(source).to_pylist()
    table[0]["word"] = None
    pq.write_table(pa.Table.from_pylist(table), source)
    with pytest.raises(ValueError, match="identity"):
        subject.prepare(source, tmp_path / "prepared", expected_sha256=digest(source))

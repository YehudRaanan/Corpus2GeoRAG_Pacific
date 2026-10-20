"""Check source-page deduplication, aliases and complete dump coverage."""

import gzip
import hashlib
import json

import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from GG_Data.pipeline.snapshot_link_relevance_probe import (
    aliases,
    dump_blocks,
    link_targets,
    linked_pages,
    measurement_pages,
    sql_string,
)


def test_aliases_use_article_join_and_follow_redirect_chains(tmp_path):
    tables = {
        "page_props": [
            {"pageid": 1, "qid": "Q1"},
            {"pageid": 2, "qid": "Q2"},
            {"pageid": 4, "qid": "Q4"},
            {"pageid": 99, "qid": "Q99"},  # Outside article namespace.
        ],
        "page": [
            {"pageid": 1, "title": "Canonical", "is_redirect": False},
            {"pageid": 2, "title": "Alias", "is_redirect": True},
            {"pageid": 4, "title": "Chain", "is_redirect": True},
        ],
        "redirect": [
            {"pageid": 2, "title": "Canonical"},
            {"pageid": 3, "title": "Canonical"},  # Outside namespace-0 page table.
            {"pageid": 4, "title": "Alias"},
        ],
    }
    for name, rows in tables.items():
        path = tmp_path / f"enwiki-test-{name}.sql.gz.test.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path)
        path.with_suffix(".json").write_text(
            json.dumps({"sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        )
    basis = measurement_pages(tmp_path, "test", {"Q1", "Q2", "Q4", "Q99"}, "enwiki")
    assert set(basis) == {"Q1", "Q2", "Q4"}  # Assigned identities stay separate.
    assert {r["qid"] for r in basis.values()} == {"Q1"}
    assert {r["pageid"] for r in basis.values()} == {1}
    assert [basis[q]["redirect_depth"] for q in ("Q1", "Q2", "Q4")] == [0, 1, 2]
    canonical = {r["title"]: str(r["pageid"]) for r in basis.values()}
    assert aliases(tmp_path, "test", canonical) == {
        "Canonical": "1",
        "Alias": "1",
        "Chain": "1",
    }
    targets = link_targets(
        [b"(10,0,'Canonical'),\n(11,0,'Alias');\n"],
        aliases(tmp_path, "test", canonical),
    )
    assert dict(
        linked_pages([b"(100,0,10),\n(100,0,11),\n(200,0,11);\n"], targets)
    ) == {"1": {100, 200}}
    # Identical page numbers in different wikis are separate identities.
    japanese = {
        "page_props": [{"pageid": 1, "qid": "Q2"}],
        "page": [{"pageid": 1, "title": "Japanese", "is_redirect": False}],
        "redirect": [],
    }
    for name, rows in japanese.items():
        path = tmp_path / f"jawiki-test-{name}.sql.gz.test.parquet"
        table = (
            pa.Table.from_pylist(rows)
            if rows
            else pa.table(
                {
                    "pageid": pa.array([], type=pa.int64()),
                    "title": pa.array([], type=pa.string()),
                }
            )
        )
        pq.write_table(table, path)
        path.with_suffix(".json").write_text(
            json.dumps({"sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        )
    basis = measurement_pages(tmp_path, "test", {"Q2"}, "jawiki")
    assert basis["Q2"]["qid"] == "Q2"
    assert aliases(tmp_path, "test", {"Japanese": "1"}, "jawiki") == {"Japanese": "1"}


def test_actual_links_count_each_page_once_across_aliases(tmp_path):
    titles = {"O'Brien": "Q1", "Alias": "Q1", "Other": "Q2"}
    assert sql_string("O'Brien") == b"'O\\'Brien'"
    targets = link_targets(
        [b"(10,0,'O\\'Brien'),\n(11,0,'Alias'),\n(12,1,'Other'),\n(13,0,'Other');\n"],
        titles,
    )
    assert targets == {10: "Q1", 11: "Q1", 13: "Q2"}
    path = tmp_path / "pagelinks.sql.gz"
    text = b"CREATE TABLE `pagelinks` (\n);\nINSERT INTO `pagelinks` VALUES\n(100,0,10),\n(100,0,11),\n(200,0,11),\n(300,1,10),\n(400,0,13),\n(999,0,110);\n-- Dump completed on 2026-10-01\n"
    with gzip.open(path, "wb") as stream:
        stream.write(text)
    path.with_name(path.name + ".verified.json").write_text(
        json.dumps(
            {
                "size": path.stat().st_size,
                "sha1": hashlib.sha1(path.read_bytes()).hexdigest(),
            }
        )
    )
    receipt = path.with_name(path.name + ".converted.json")
    receipt.write_text(json.dumps({"scanned_rows": 6}))
    updates = []
    pages = linked_pages(
        dump_blocks(path, "pagelinks", lambda **v: updates.append(v), block_size=17),
        targets,
    )
    assert dict(pages) == {"Q1": {100, 200}, "Q2": {400}}
    assert len(pages["Q1"] & {100}) / len(pages["Q1"]) == 0.5
    assert updates[-1]["verified"] and updates[-1]["scanned_rows"] == 6
    receipt.write_text(json.dumps({"scanned_rows": 7}))
    with pytest.raises(ValueError, match="coverage differs"):
        list(dump_blocks(path, "pagelinks", lambda **v: None, block_size=17))


def test_population_filter_exceeds_windows_command_limit():
    # Regression for WinError 206: realistic target count and ID lengths.
    targets = {100000000 + i: "1" for i in range(9000)}
    assert len("|".join(map(str, targets))) > 32767
    blocks = [
        b"(100,0,100000000),\n(100,0,100008999),\n(200,0,100008999),\n"
        b"(300,1,100000000),\n(400,0,100009000),\n(500,0,1000000000);\n"
    ]
    assert dict(linked_pages(blocks, targets)) == {"1": {100, 200}}

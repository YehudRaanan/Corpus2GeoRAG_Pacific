"""Checks for source preservation and fail-closed dump import."""

import gzip
import json
import os
from concurrent.futures import ProcessPoolExecutor

import pyarrow.parquet as pq
import pytest

from wikipedia_dump_bigquery import (
    DATE,
    canonical_page,
    convert,
    parse_tuple,
    prepare_links,
    prepare_metadata,
    project_row,
)


@pytest.mark.parametrize(
    "pageid,is_redirect,expected",
    [
        ("16554732", "false", True),
        ("16554732", False, True),
        ("1", "true", False),
        ("1", True, False),
        (None, None, False),
    ],
)
def test_canonical_page_handles_cli_boolean_strings(pageid, is_redirect, expected):
    assert canonical_page({"pageid": pageid, "is_redirect": is_redirect}) is expected


def test_mysql_strings_preserve_japanese_quotes_symbols_and_null():
    assert parse_tuple(
        r"(1,'日本, (東京)','O\'Brien','a\\b','a\nb','It''s',NULL,1.2e-3);"
    ) == ["1", "日本, (東京)", "O'Brien", "a\\b", "a\nb", "It's", None, "1.2e-3"]
    with pytest.raises(ValueError):
        parse_tuple("(1,unexpected_function());")


def write_links(path, footer=True):
    text = """CREATE TABLE `pagelinks` (
  `pl_from` int NOT NULL,
  `pl_from_namespace` int NOT NULL,
  `pl_target_id` bigint NOT NULL
) ENGINE=InnoDB;
INSERT INTO `pagelinks` VALUES
(10,0,120),
(11,0,121),
(10,1,122);
"""
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(text + ("-- Dump completed on 2026-10-01\n" if footer else ""))


def test_conversion_respects_source_and_namespace_and_reuses_cache(tmp_path):
    path = tmp_path / "pagelinks.sql.gz"
    write_links(path)
    parquet, count = convert(path, "pagelinks", {10})
    assert count == 1
    assert pq.read_table(parquet).to_pylist() == [{"pageid": 10, "target_id": 120}]
    assert convert(path, "pagelinks", {10}) == (parquet, count)
    saved = json.loads(parquet.with_suffix(".json").read_text())
    assert saved["scanned_rows"] == 3


def test_incomplete_dump_is_never_promoted(tmp_path):
    path = tmp_path / "pagelinks.sql.gz"
    write_links(path, footer=False)
    with pytest.raises(ValueError, match="Incomplete SQL dump"):
        convert(path, "pagelinks", {10})
    assert not list(tmp_path.glob("*.json"))
    assert not [p for p in tmp_path.glob("*.parquet") if ".partial." not in p.name]


def test_foreign_redirects_and_invalid_qids_are_not_accepted():
    assert (
        project_row(
            "redirect",
            {
                "rd_namespace": "0",
                "rd_interwiki": "en",
                "rd_from": "1",
                "rd_title": "Other wiki",
            },
        )
        is None
    )
    with pytest.raises(ValueError, match="Invalid dumped Wikidata ID"):
        project_row(
            "page_props",
            {"pp_propname": "wikibase_item", "pp_page": "1", "pp_value": "not-QID"},
        )


@pytest.mark.parametrize("invalid_qid", [False, True])
def test_binary_properties_are_skipped_but_qids_must_be_utf8(tmp_path, invalid_qid):
    path = tmp_path / "page_props.sql.gz"
    header = b"""CREATE TABLE `page_props` (
  `pp_page` int NOT NULL,
  `pp_propname` varbinary(60) NOT NULL,
  `pp_value` blob NOT NULL,
  `pp_sortkey` float DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `page_props` VALUES
"""
    qid = b"Q\x8b" if invalid_qid else b"Q49112"
    with gzip.open(path, "wb") as stream:
        stream.write(
            header
            + b"(1,'templatedata','\x1f\x8b',NULL),\n"
            + b"(2,'wikibase_item','"
            + qid
            + b"',NULL),\n"
            + b"(3,'templatedata','\x1f\x8b',NULL);\n"
            + b"-- Dump completed on 2026-10-01\n"
        )
    if invalid_qid:
        with pytest.raises(UnicodeDecodeError):
            convert(path, "page_props")
        assert not list(tmp_path.glob("*.json"))
    else:
        parquet, count = convert(path, "page_props")
        assert count == 1
        assert pq.read_table(parquet).to_pylist() == [{"pageid": 2, "qid": "Q49112"}]
        assert json.loads(parquet.with_suffix(".json").read_text())["scanned_rows"] == 3


def test_process_workers_preserve_both_languages_and_selected_link_scope(tmp_path):
    for lang, title in [("en", "Example"), ("ja", "日本")]:
        tables = {
            "page": (
                "page_id page_namespace page_title page_is_redirect page_latest page_links_updated",
                f"(10,0,'{title}',0,100,NULL);",
            ),
            "redirect": (
                "rd_from rd_namespace rd_title rd_interwiki",
                f"(11,0,'{title}','');",
            ),
            "page_props": (
                "pp_page pp_propname pp_value pp_sortkey",
                "(10,'wikibase_item','Q17',NULL);",
            ),
            "pagelinks": (
                "pl_from pl_from_namespace pl_target_id",
                "(10,0,100),\n(10,0,101),\n(10,0,102),\n(99,0,103);",
            ),
            "linktarget": (
                "lt_id lt_namespace lt_title",
                f"(100,0,'{title}'),\n(101,1,'Talk');",
            ),
        }
        for table, (columns, values) in tables.items():
            fields = ",\n".join(f"  `{name}` text" for name in columns.split())
            with gzip.open(
                tmp_path / f"{lang}wiki-{DATE}-{table}.sql.gz", "wt", encoding="utf-8"
            ) as stream:
                stream.write(
                    f"CREATE TABLE `{table}` (\n{fields}\n) ENGINE=InnoDB;\n"
                    f"INSERT INTO `{table}` VALUES\n{values}\n"
                    "-- Dump completed on 2026-10-01\n"
                )
    with ProcessPoolExecutor(max_workers=2) as workers:
        jobs = [
            workers.submit(prepare_metadata, tmp_path, lang) for lang in ("en", "ja")
        ]
        assert [job.result(timeout=30) for job in jobs] == ["en", "ja"]
        for lang in ("en", "ja"):
            saved = json.loads((tmp_path / f"progress_{lang}.json").read_text())
            assert saved["stage"] == "METADATA_FILES_READY"
            assert saved["pid"] != os.getpid()
        jobs = [
            workers.submit(prepare_links, tmp_path, lang, {10}) for lang in ("en", "ja")
        ]
        for job in jobs:
            lang, targets, inventory = job.result(timeout=30)
            assert targets == {100, 101, 102}
            assert inventory == {
                "source_pages": 1,
                "distinct_link_targets": 3,
                "target_namespace_counts": {0: 1, 1: 1},
                "missing_target_ids": [102],
            }
            path, count = convert(tmp_path / f"{lang}wiki-{DATE}-page.sql.gz", "page")
            assert count == 1
            assert pq.read_table(path)["title"].to_pylist() == [
                "Example" if lang == "en" else "日本"
            ]

"""Checks for source preservation and fail-closed dump import."""

import gzip
import json

import pyarrow.parquet as pq
import pytest

from wikipedia_dump_bigquery import convert, parse_tuple, project_row


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

"""Population S2T 8: exact native additions preserve the existing catalog."""

from pathlib import Path

import pytest

from GG_Data.mapping import build_relation_mapping_v2_1 as catalog
from GG_Data.mapping.build_relation_mapping_v2_1 import OUT, build, read_csv

RULES = OUT / "ADDITIONAL_NATIVE_RELATION_RULES_2026-10-20.csv"


def test_relative_native_paths_match_absolute_build(tmp_path, monkeypatch):
    monkeypatch.chdir(catalog.ROOT)
    prior = OUT / "RELATION_DIRECTION_CATALOG_v2.1.1.csv"
    relative = tmp_path / "relative"
    absolute = tmp_path / "absolute"
    for directory, native, directions in (
        (relative, RULES.relative_to(catalog.ROOT), prior.relative_to(catalog.ROOT)),
        (absolute, RULES, prior),
    ):
        directory.mkdir()
        build(
            native_rules=native,
            prior_directions=directions,
            version="relation-map-v2.1.2",
            output=directory,
        )
    for path in relative.iterdir():
        assert path.read_bytes() == (absolute / path.name).read_bytes()


def test_native_extension_preserves_existing_rules_and_reverse_contract(tmp_path: Path):
    # Rebuild the historical version only in a temporary directory. No data,
    # network, assertions or original catalog files are changed by this test.
    build(output=tmp_path)
    filenames = (
        "RELATION_MAPPING_TABLE",
        "RELATION_DIRECTION_CATALOG",
        "RELATION_DIRECTION_LOOKUP",
    )
    for name in filenames:
        assert (tmp_path / f"{name}_v2.1.0.csv").read_bytes() == (
            OUT / f"{name}_v2.1.0.csv"
        ).read_bytes()

    summary = build(native_rules=RULES, version="relation-map-v2.1.1", output=tmp_path)
    assert summary["source_mapping_rows"] == 1596
    for name, key in zip(
        filenames, ("source_predicate", "level2_relation_id", "input_relation_id")
    ):

        def row_key(row):
            return (row["source"], row[key]) if "source" in row else row[key]

        old = {row_key(r): r for r in read_csv(OUT / f"{name}_v2.1.0.csv")}
        new = {row_key(r): r for r in read_csv(tmp_path / f"{name}_v2.1.1.csv")}
        for code, row in old.items():
            expected = {**row, "relation_map_version": "relation-map-v2.1.1"}
            # P2341 already has an EventKG source entry. Adding the native
            # source updates this shared definition's provenance/counts only.
            if row.get("level2_relation_id") == "wd:P2341":
                expected["prior_v2_reverse_policy"] = (
                    "INBOUND_TRAVERSAL_ONLY|RESOLVED_BY_V2_1_DATA_LAYER_CONTRACT"
                )
                if name == "RELATION_DIRECTION_CATALOG":
                    expected.update(source_relation_rows="2", source_occurrences="2")
            assert new[code] == expected

    mapping = read_csv(tmp_path / "RELATION_MAPPING_TABLE_v2.1.1.csv")
    row = next(r for r in mapping if r["source_predicate"] == "wd:P2341")
    assert row["source"] == "Wikidata"
    assert row["normalized_relation_id"] == row["level2_relation_id"] == "wd:P2341"
    assert row["direction_to_level2"] == "same"
    assert row["level1_family"] == "UNRESOLVED"
    assert row["level1_assignment_status"] == "NOT_ASSIGNED"
    assert row["level2_relation_label"] == "indigenous to"
    assert row["reverse_relation_id"] == "inverse:wd:P2341"
    lookup = {
        r["input_relation_id"]: r
        for r in read_csv(tmp_path / "RELATION_DIRECTION_LOOKUP_v2.1.1.csv")
    }
    assert lookup["wd:P2341"]["output_reverse_relation_id"] == "inverse:wd:P2341"
    assert lookup["inverse:wd:P2341"]["output_reverse_relation_id"] == "wd:P2341"


def test_native_additions_cannot_overwrite_historical_version(tmp_path: Path):
    with pytest.raises(ValueError, match="new mapping version"):
        build(native_rules=RULES, output=tmp_path)
    assert not list(tmp_path.iterdir())


def test_new_native_name_keeps_approved_existing_reverse_label(tmp_path, monkeypatch):
    # Reproduce the real P10888 display-name issue with fixture statements.
    # No source assertions are retrieved or written by this unit test.
    original_read = catalog.read_csv

    def fixture_read(path):
        rows = original_read(path)
        if path == RULES:
            extra = {**rows[0]}
            extra.update(
                rule_id="fixture-P10888",
                source_predicate="wd:P10888",
                normalized_relation_id="wd:P10888",
                level2_relation_id="wd:P10888",
                relation_label="contains the statistical territorial entity",
                statement_ids="Q1$fixture",
            )
            rows.append(extra)
        return rows

    monkeypatch.setattr(catalog, "read_csv", fixture_read)
    build(
        native_rules=RULES,
        version="relation-map-v2.1.2",
        output=tmp_path,
        prior_directions=OUT / "RELATION_DIRECTION_CATALOG_v2.1.1.csv",
    )
    rows = original_read(tmp_path / "RELATION_MAPPING_TABLE_v2.1.2.csv")
    p8138 = next(
        r
        for r in rows
        if r["source"] == "Wikidata" and r["source_predicate"] == "wd:P8138"
    )
    assert (
        p8138["reverse_relation_label"]
        == "inverse of located in the statistical territorial entity"
    )
    assert p8138["reverse_label_source"] == "DERIVED_FROM_LEVEL2_LABEL"
    p10888 = next(
        r
        for r in rows
        if r["source"] == "Wikidata" and r["source_predicate"] == "wd:P10888"
    )
    assert p10888["level2_relation_label"] == p8138["reverse_relation_label"]
    assert p10888["relation_label"] == "contains the statistical territorial entity"

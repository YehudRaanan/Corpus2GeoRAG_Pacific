"""Population S2T 8: exact native additions preserve the existing catalog."""

from pathlib import Path

import pytest

from GG_Data.mapping.build_relation_mapping_v2_1 import OUT, build, read_csv

RULES = OUT / "ADDITIONAL_NATIVE_RELATION_RULES_2026-10-20.csv"


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

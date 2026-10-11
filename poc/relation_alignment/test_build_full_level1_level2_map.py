import csv

from build_full_level1_level2_map import INPUT, build


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_full_map_has_every_eligible_relation(tmp_path) -> None:
    report = tmp_path / "report.md"
    summary = build(INPUT, tmp_path, report)
    mapped = read_rows(tmp_path / "level1_level2_map.csv")
    candidates = read_rows(tmp_path / "level1_candidate_rankings.csv")

    assert len(mapped) == summary["distinct_level2_relations"] == 1106
    assert len({row["canonical_level2_id"] for row in mapped}) == len(mapped)
    assert summary["eligible_rows_represented_in_map"] == 1520
    assert summary["unmapped_level2_relations"] == 0
    assert len(candidates) == summary["ranked_review_assignments"] * 14
    assert all(row["level1_family"] != "UNASSIGNED_REVIEW" for row in mapped)

    country_rows = {
        row["canonical_level2_id"]: row
        for row in mapped
        if row["canonical_level2_id"] in {"wd:P17", "wd:P495", "wd:P8047"}
    }
    assert set(country_rows) == {"wd:P17", "wd:P495", "wd:P8047"}
    assert {
        row["evaluation_acceptance_group"] for row in country_rows.values()
    } == {"COUNTRY_ASSOCIATION"}

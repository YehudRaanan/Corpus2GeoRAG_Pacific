import csv

from build_common_relation_map import OUT, build


def rows(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_build_preserves_rows_and_adds_only_unambiguous_merges() -> None:
    summary = build()
    source_rows = rows("common_relation_source_map.csv")

    assert summary["input_source_relation_rows"] == summary["output_source_relation_rows"]
    assert summary["new_provisional_source_mappings"] == 7
    assert summary["common_ids_reduced_by"] == 7

    by_predicate = {row["source_predicate"]: row for row in source_rows}
    assert (
        by_predicate["http://yago-knowledge.org/resource/hasWonPrize"][
            "common_relation_id"
        ]
        == "wd:P166"
    )
    assert (
        by_predicate["http://semanticweb.cs.vu.nl/2009/11/sem/hasSubEvent"][
            "common_relation_id"
        ]
        == "wd:P527"
    )

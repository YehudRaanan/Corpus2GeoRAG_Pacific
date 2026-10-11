import csv

from analyze_unresolved_common_relations import OUT, build


def read_rows(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_unresolved_eda_covers_every_native_only_relation() -> None:
    summary = build()
    relations = read_rows("unresolved_relation_summary.csv")
    options = read_rows("observed_candidate_options.csv")

    assert len(relations) == summary["unresolved_source_relation_rows"] == 435
    assert len(options) == summary["observed_candidate_option_rows"]
    assert all(row["eda_status"] for row in relations)
    assert all(row["candidate_common_relation_id"].startswith("wd:P") for row in options)
    assert summary["classifier_run"] is False

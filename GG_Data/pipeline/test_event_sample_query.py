"""A filtered test must not replace held entities or alter other types."""

import json

import pytest

from GG_Data.pipeline.event_sample_query import filtered_sample
from GG_Data.pipeline.poc import digest
from GG_Data.pipeline.scope_concentration_filter import combine_language_rows


def test_filtered_sample_keeps_non_misc_holds_unknown_and_checks_evidence(tmp_path):
    def row(qid, wiki, denominator):
        return dict(
            qid=qid,
            name=qid,
            wiki=wiki,
            scope_linking_pages=1 if denominator else None,
            all_linking_pages=denominator,
            relevance=1 / denominator if denominator else None,
            score_status="SCORED" if denominator else "UNAVAILABLE_SNAPSHOT_PAGE",
        )

    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    english = [
        row("Q1", "enwiki", 100),
        row("Q2", "enwiki", 100),
        row("Q3", "enwiki", None),
    ]
    japanese = [
        row("Q1", "jawiki", 10),
        row("Q2", "jawiki", None),
        row("Q3", "jawiki", None),
    ]
    # Separate source files model unchanged per-language acquisition evidence.
    for wiki, rows in (("enwiki", english), ("jawiki", japanese)):
        (tmp_path / wiki).mkdir()
        save(f"{wiki}/report.json", dict(wiki=wiki, rows=rows))
    sources = [tmp_path / wiki / "report.json" for wiki in ("enwiki", "jawiki")]
    selection = save(
        "selection.json",
        dict(
            status="COMPLETE_MAXIMUM_LANGUAGE_THRESHOLD",
            inputs={str(p): digest(p) for p in sources},
            outputs={},
            rows=combine_language_rows(english, japanese),
        ),
    )
    sample = save("sample.json", dict(daniel_qids=["Q1", "Q2", "Q3", "Q4"]))
    before = digest(sample)
    kept, evidence = filtered_sample(selection, sample)
    assert kept == ["Q1", "Q4"]
    assert evidence["below_threshold_qids"] == ["Q2"]
    assert evidence["held_unknown_qids"] == ["Q3"]
    assert digest(sample) == before
    sources[0].write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="language evidence changed"):
        filtered_sample(selection, sample)

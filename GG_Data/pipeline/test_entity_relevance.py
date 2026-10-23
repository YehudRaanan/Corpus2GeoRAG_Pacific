"""Entity columns reuse page/QID counts; synthetic importance is separate."""

import copy
import gzip
import json

import pytest

from GG_Data.pipeline.entity_relevance import attach, records, reuse_languages
from GG_Data.pipeline.poc import digest


def report(wiki, numerator, denominator):
    return {
        "wiki": wiki,
        "dump_date": "20261001",
        "rows": [
            dict(
                wiki=wiki,
                qid="Q1",
                name="One",
                scope_linking_pages=numerator,
                all_linking_pages=denominator,
                relevance=numerator / denominator,
                score_status="SCORED",
            )
        ],
    }


def test_language_maximum_and_separate_typed_entities():
    measured = records(report("enwiki", 1, 100), report("jawiki", 2, 10), {})
    rows = [
        dict(entity_id="Q1", type=t, attributes={"keep": True}) for t in ("LOC", "ORG")
    ]
    rows += [dict(entity_id="SYN_test", type="LOC", importance=1)]
    before = copy.deepcopy(rows)
    result = attach(rows, measured)
    assert rows == before
    for row in result[:2]:
        assert (row["relevance_en"], row["relevance_ja"], row["relevance"]) == (
            0.01,
            0.2,
            0.2,
        )
        assert row["attributes"]["relevance_basis"]["maximum_score_wiki"] == "jawiki"
        assert row["attributes"]["keep"] is True
    assert result[2]["relevance"] is None
    assert result[2]["relevance_status"] == "NOT_APPLICABLE_SYNTHETIC"
    assert result[2]["importance"] == 1


def test_unmeasured_is_visible_and_snapshot_mismatch_stops():
    assert attach([dict(entity_id="Q1")], {})[0]["relevance_status"] == "UNMEASURED"
    japanese = report("jawiki", 1, 10)
    japanese["dump_date"] = "other"
    with pytest.raises(ValueError, match="different snapshots"):
        records(report("enwiki", 1, 100), japanese, {})


def test_reuse_counts_preserves_rows_and_rejects_changed_evidence(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("{}", encoding="utf-8")
    measured = records(
        report("enwiki", 1, 100),
        report("jawiki", 2, 10),
        {str(source): digest(source)},
    )
    path = tmp_path / "matching_relevance.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(measured, stream)
    (tmp_path / "report.json").write_text(
        json.dumps({"outputs": {path.name: digest(path)}}), encoding="utf-8"
    )
    output = tmp_path / "reused"
    output.mkdir()
    result = reuse_languages(path, {"Q1"}, output)
    assert result[0]["rows"] == report("enwiki", 1, 100)["rows"]
    assert result[1]["rows"] == report("jawiki", 2, 10)["rows"]
    assert all(r["network_requests"] == 0 for r in result)
    with pytest.raises(ValueError, match="lack candidate relevance"):
        reuse_languages(path, {"Q2"}, output)
    source.write_text('{"changed":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="language report changed"):
        reuse_languages(path, {"Q1"}, output)

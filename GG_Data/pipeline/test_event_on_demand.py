"""Only candidate-required class paths are fetched, cached and classified."""

import json
import re

import pytest

from GG_Data.pipeline import event_on_demand as stage
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException


def test_native_record_fallback_preserves_statement_rank(tmp_path, monkeypatch):
    """Both graphs lack the item; the native record supplies complete evidence."""
    monkeypatch.setattr(
        stage.events,
        "cached_json",
        lambda *args: (
            {
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q10"},
                            "present": {"value": "false"},
                        }
                    ]
                }
            },
            {},
        ),
    )
    statement_id = "Q10$11111111-1111-1111-1111-111111111111"
    record = dict(
        id="Q10",
        claims={
            "P31": [
                dict(
                    id=statement_id,
                    rank="deprecated",
                    mainsnak=dict(
                        property="P31",
                        datatype="wikibase-item",
                        datavalue=dict(value={"entity-type": "item", "id": "Q20"}),
                    ),
                )
            ]
        },
    )
    monkeypatch.setattr(stage.events, "current_record", lambda *args: (record, {}))
    receipts = []
    result = stage.fetch_classes(tmp_path, ["Q10"], "P31", receipts.append)
    assert result == {
        "Q10": [
            dict(
                parent="Q20",
                statement=stage.statement_key(statement_id),
                rank="deprecated",
            )
        ]
    }
    assert len(receipts) == 3 and receipts[-1]["native_fallback"]


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("filtered", [False, True])
def test_candidate_only_paths_and_stop(tmp_path, monkeypatch, failure, filtered):
    monkeypatch.setattr(stage, "ROOT", tmp_path)
    root = tmp_path / "GG_Data/pipeline/outputs"
    candidates, measurement, saved = [root / p for p in ("ids", "measure", "stopped")]
    for p in (candidates, measurement, saved):
        p.mkdir(parents=True)
        (p / "report.json").write_text("{}")
    (candidates / "verification.json").write_text("{}")
    monkeypatch.setattr(
        stage, "candidate_universe", lambda *args: {f"Q{n}" for n in range(10, 16)}
    )
    # The filtered sample uses its complete inventory, not a 165/200-item cap.
    # Complete saved P31 answers are reused without requesting them again.
    monkeypatch.setattr(
        stage,
        "filtered_candidate_universe",
        lambda source: (
            {f"Q{n}" for n in range(10, 16)},
            {"retained_daniel_qids": ["Q1", "Q2"]},
            {
                "P31": {"Q10": [dict(parent="Q20", rank="normal")]},
                "P279": {},
            },
        ),
    )
    (candidates / "candidate_restriction.json").write_text("{}")
    # Reuse only a positive path from the stopped catalog, never its absences.
    (saved / "catalog.json").write_text(
        json.dumps(
            dict(
                edges=[
                    dict(
                        subject_qid="Q20",
                        object_qid=stage.events.EVENT_ROOT,
                        source_record_id="Q20-saved",
                        rank="normal",
                    )
                ]
            )
        )
    )
    (saved / "report.json").write_text(
        json.dumps(
            dict(
                status="STOPPED_FOR_USER_APPROVED_ON_DEMAND_SWITCH",
                queries=[],
                outputs={"catalog.json": digest(saved / "catalog.json")},
            )
        )
    )
    calls = []

    def cached(store, url, params):
        query = params["query"]
        batch = re.findall(r"wd:(Q\d+)", query)
        prop = "P31" if "p:P31" in query else "P279"
        calls.append((prop, tuple(batch), url))
        if failure and url == stage.events.SCHOLARLY_QUERY_URL:
            raise SourceException("timeout")
        rows = []
        uri = "http://www.wikidata.org/entity/"
        for qid in batch:
            base = dict(
                item={"value": uri + qid},
                present={"value": "true" if url == stage.events.QUERY_URL else "false"},
            )
            if url == stage.events.SCHOLARLY_QUERY_URL:
                rows.append(base)
                continue
            edges = []
            if prop == "P31":
                parent = {
                    "Q10": "Q20",
                    "Q11": "Q21",
                    "Q12": "Q20",
                    "Q13": "Q21",
                    "Q14": "Q24",
                    "Q15": "Q24",
                }[qid]
                edges = [(parent, "Normal")]
            elif qid == "Q21":
                edges = [("Q21", "Normal"), (stage.events.EVENT_ROOT, "Deprecated")]
            elif qid == "Q24":
                edges = [(stage.events.EVENT_ROOT, "Preferred")]
            else:
                pytest.fail(f"Fetched unrelated or already proven class {qid}")
            for i, (parent, rank) in enumerate(edges):
                row = dict(
                    base,
                    parent={"value": uri + parent},
                    statement={
                        "value": uri
                        + f"statement/{qid}-{i}1111111-1111-1111-1111-111111111111"
                    },
                    rank={"value": f"http://wikiba.se/ontology#{rank}Rank"},
                )
                rows.append(row)
        return {"results": {"bindings": rows}}, {"request": {"url": url}}

    monkeypatch.setattr(stage.events, "cached_json", cached)
    output = root / "new"
    result = stage.run(
        candidates,
        None if filtered else measurement,
        saved,
        root / "store",
        output,
        filtered_sample=filtered,
    )
    assert result["status"].startswith("BLOCKED") == failure
    assert result["classification_complete"] is (not failure)
    assert not result["events_complete"] and result["event_rows_written"] == 0
    rows = [
        json.loads(line)
        for line in (output / "classifications.jsonl").read_text().splitlines()
    ]
    if failure:
        assert len(calls) == 2 and rows == [] and result["candidates_classified"] == 0
    else:
        assert [row["event_hierarchy_match"] for row in rows] == [
            True,
            False,
            True,
            False,
            True,
            True,
        ]
        assert (
            result["candidates_classified"] == 6
            and result["hierarchy_positive_count"] == 4
        )
        assert len(calls) == 6  # two graphs each for P31 and two reused P279 nodes
        assert set(read_json(output / "class_parents.json")) == {"Q21", "Q24"}
    if filtered:
        assert all("Q10" not in batch for prop, batch, _ in calls if prop == "P31")
        assert result["filter_evidence"]["retained_daniel_qids"] == ["Q1", "Q2"]
    # Missing candidate rows are an incomplete response, not a negative result.
    with pytest.raises(SourceException, match="Incomplete"):
        stage.class_answers({"results": {"bindings": []}}, ["Q10"], "P31")

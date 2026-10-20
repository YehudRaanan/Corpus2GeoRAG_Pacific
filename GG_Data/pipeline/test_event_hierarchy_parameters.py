"""Complete export, rank filtering and source-stop gates for Event parameters."""

import csv
import json
import sqlite3

import pytest

from GG_Data.pipeline import event_hierarchy_parameters as stage
from GG_Data.pipeline.poc import read_json
from GG_Data.pipeline.relations import SourceException


def binding(child, parent, rank="normal", token="1111"):
    uri = "http://www.wikidata.org/entity/"
    values = dict(
        subject=uri + child,
        parent=uri + parent,
        property=uri + "P279",
        statement=uri + f"statement/{child}-{token}",
        rank=f"http://wikiba.se/ontology#{rank.title()}Rank",
    )
    return {k: {"value": v} for k, v in values.items()}


def test_export_closure_keeps_both_ranks_and_stops_cycles(tmp_path):
    with sqlite3.connect(":memory:") as db:
        stage.create_edge_table(db)
        rows = [
            ("Q2", stage.events.EVENT_ROOT, "normal"),
            ("Q3", "Q2", "preferred"),
            ("Q2", "Q3", "normal"),
            ("Q9", stage.events.EVENT_ROOT, "deprecated"),
            ("Q8", "Q9", "normal"),
        ]
        for i, (child, parent, rank) in enumerate(rows):
            db.execute(
                "INSERT INTO hierarchy_edges VALUES(?,?,?,?,?,?,?)",
                (
                    str(i),
                    child,
                    parent,
                    rank,
                    f"native-{i}",
                    stage.SERVICES[i % 2],
                    "2026-10-20T00:00:00Z",
                ),
            )
        with pytest.raises(SourceException, match="Complete hierarchy"):
            stage.export_parameters(db, tmp_path, False)
        assert not (tmp_path / "event_types.csv").exists()
        counts = stage.export_parameters(db, tmp_path, True)
        assert counts == {"event_types.csv": 3, "event_hierarchy_mapping.csv": 3}
        assert {r[0] for r in db.execute("SELECT qid FROM event_types")} == {
            stage.events.EVENT_ROOT,
            "Q2",
            "Q3",
        }
        assert db.execute("SELECT COUNT(*) FROM hierarchy_edges").fetchone()[0] == 5
        with (tmp_path / "event_hierarchy_mapping.csv").open(newline="") as f:
            assert {r["statement_rank"] for r in csv.DictReader(f)} == {
                "normal",
                "preferred",
            }


def test_page_order_and_cursor_are_verified():
    rows = [binding("Q2", "Q1"), binding("Q3", "Q1")]
    data = dict(results=dict(bindings=rows))
    assert len(stage.page_links(data, None)) == 2
    with pytest.raises(SourceException, match="unordered"):
        stage.page_links(dict(results=dict(bindings=rows[::-1])), None)
    with pytest.raises(SourceException, match="unordered"):
        stage.page_links(data, rows[0]["statement"]["value"])
    with pytest.raises(ValueError, match="cursor"):
        stage.bulk_page_query("malformed")
    query = stage.bulk_page_query()
    assert "COUNT" not in query and "wdt:" not in query
    assert "ORDER BY STR(?statement)" in query


@pytest.mark.parametrize("fail", [False, True])
def test_complete_services_required_before_filter(tmp_path, monkeypatch, fail):
    monkeypatch.setattr(stage, "ROOT", tmp_path)
    output = tmp_path / "GG_Data/pipeline/outputs/parameters"
    calls = []

    def fetch(store, url, params):
        calls.append(url)
        if fail and url == stage.SERVICES[1]:
            raise SourceException("test source failure")
        rows = (
            [binding("Q2", stage.events.EVENT_ROOT)]
            if url == stage.SERVICES[0]
            else [binding("Q3", "Q2", "preferred")]
        )
        return dict(results=dict(bindings=rows)), dict(
            retrieved_at="2026-10-20T00:00:00Z"
        )

    monkeypatch.setattr(stage.events, "cached_json", fetch)
    result = stage.run(output.parent / "store", output)["hierarchy"]
    assert calls == list(stage.SERVICES)
    assert result["parameter_table_usable"] is not fail
    assert result["hierarchy_elapsed_seconds"] >= 0
    if fail:
        assert not (output / "event_types.csv").exists()
        assert not result["filter_started"]
        with pytest.raises(SourceException, match="Incomplete Event parameters"):
            stage.filter_candidates(output, output, output)
    else:
        monkeypatch.setattr(
            stage,
            "filtered_candidate_universe",
            lambda _: (
                {"Q10", "Q20"},
                {},
                {
                    "P31": {
                        "Q10": [dict(rank="normal", parent="Q3")],
                        "Q20": [dict(rank="deprecated", parent="Q3")],
                    }
                },
            ),
        )
        result = stage.filter_candidates(output, output, output)
        assert result["classification_complete"]
        assert result["candidates_classified"] == 2
        assert result["hierarchy_positive_count"] == 1
        assert result["filter_elapsed_seconds"] >= 0
        assert not result["events_complete"]
        assert result["event_rows_written"] == 0
        rows = [
            json.loads(r)
            for r in (output / "filter/classifications.jsonl").read_text().splitlines()
        ]
        assert [r["event_hierarchy_match"] for r in rows] == [True, False]
        assert read_json(output / "filter/report.json")["classification_complete"]

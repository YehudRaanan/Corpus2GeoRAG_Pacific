"""Check score lineage, uncapped Events and the strict mutual assertion budget."""

import copy

import pytest

from GG_Data.pipeline.relation_selection import (
    attach_importance,
    importance,
    select,
    temporal_group,
)
from GG_Data.pipeline.relations import SourceException


def edge(index, subject, target):
    return dict(
        observation_id=str(index), subject_entity_id=subject, object_entity_id=target
    )


def test_counts_original_mentions_and_source_pages_without_type_or_counterpart_fanout():
    mentions = [
        dict(
            mention_id=str(i), entity_id=qid, raw=dict(entity_group=kind, Source=source)
        )
        for i, (qid, kind, source) in enumerate(
            [
                ("Q1", "ORG", "Page A"),
                ("Q1", "LOC", "Page A"),
                ("Q1", "ORG", "Page B"),
                ("Q2", "DATE", "Page A"),
                ("SYN_3", "LOC", "Page C"),
                ("SYN_DATE_4", "DATE", "Page D"),
                (None, "DATE", "Page D"),
            ]
        )
    ]
    assert importance(mentions) == {
        "Q1": dict(
            distinct_source_pages=2,
            total_mentions=3,
            score=6,
            source_pages=["Page A", "Page B"],
        ),
        "SYN_3": dict(
            distinct_source_pages=1, total_mentions=1, score=1, source_pages=["Page C"]
        ),
        "SYN_DATE_4": dict(
            distinct_source_pages=1, total_mentions=1, score=1, source_pages=["Page D"]
        ),
    }
    with pytest.raises(SourceException, match="Repeated original mention"):
        importance(mentions + [mentions[0]])
    with pytest.raises(SourceException, match="Synthetic identity reused"):
        importance(mentions + [{**mentions[4], "mention_id": "new-mention"}])


def test_mutual_selection_no_refill_event_exemption_and_source_preservation():
    # Q1 chooses Q2, but Q2 has 20 stronger neighbors and rejects this assertion.
    rows = [edge(0, "Q1", "Q2")]
    rows += [edge(i, "Q2", f"Q{100+i}") for i in range(1, 21)]
    rows += [edge(30 + i, "Q3", f"Q{200+i}") for i in range(21)]
    rows += [edge(90, "Q3", "Q4"), edge(91, "Q2", "Q2")]
    scores = {
        qid: dict(score=int(qid[1:]))
        for row in rows
        for qid in (row["subject_entity_id"], row["object_entity_id"])
    }
    original = copy.deepcopy(rows)
    kept, audit = select(rows, scores, {"Q3", "Q4"}, event_population_complete=True)
    assert rows == original
    assert "0" not in {row["observation_id"] for row in kept}
    assert len([row for row in kept if row["subject_entity_id"] == "Q3"]) == 22
    assert len([row for row in kept if row["subject_entity_id"] == "Q2"]) == 20
    assert audit[0]["endpoint_selections"] == {"Q1": True, "Q2": False}
    with pytest.raises(SourceException, match="Complete Event membership"):
        select(rows, scores, set(), event_population_complete=False)


def test_equal_cutoff_scores_stop_and_multiple_assertions_spend_separate_slots():
    rows = [edge(i, "Q1", "Q2") for i in range(21)]
    scores = {"Q1": dict(score=1), "Q2": dict(score=2)}
    with pytest.raises(SourceException, match="Unapproved importance tie"):
        select(rows, scores, set(), event_population_complete=True)
    kept, _ = select(rows[:20], scores, set(), event_population_complete=True)
    assert kept == rows[:20]
    with pytest.raises(SourceException, match="unique base assertions"):
        select(rows[:1] * 2, scores, set(), event_population_complete=True)
    with pytest.raises(SourceException, match="Missing Daniel importance"):
        select(rows[:1], {}, set(), event_population_complete=True)


def test_entity_score_preserves_types_raw_evidence_and_scores_synthetic():
    rows = [
        dict(entity_id=qid, type=kind, attributes={"original": ["evidence"]})
        for qid, kind in [("Q1", "LOC"), ("Q1", "ORG"), ("SYN_1", "MISC")]
    ]
    original = copy.deepcopy(rows)
    scores = {
        "Q1": dict(distinct_source_pages=2, total_mentions=3, score=6),
        "SYN_1": dict(distinct_source_pages=1, total_mentions=1, score=1),
    }
    result = attach_importance(rows, scores, "population-hash")
    assert rows == original
    assert [r["importance"] for r in result] == [6, 6, 1]
    for prior, current in zip(original, result):
        assert current["attributes"]["original"] == prior["attributes"]["original"]
        assert current["entity_id"] == prior["entity_id"]
        assert current["type"] == prior["type"]
        assert (
            current["attributes"]["importance_basis"]["population_sha256"]
            == "population-hash"
        )
    assert result[-1]["attributes"]["importance_basis"]["status"] == "SCORED"
    with pytest.raises(SourceException, match="Entity importance missing"):
        attach_importance(rows, {}, "population-hash")
    with pytest.raises(SourceException, match="Repeated Entity identity"):
        attach_importance(rows + rows[:1], scores, "population-hash")
    with pytest.raises(SourceException, match="already supplied"):
        attach_importance(result, scores, "population-hash")


def test_period_first_undated_fill_and_outside_evidence_preserved():
    # Nineteen low-importance dated assertions outrank a higher-scored undated
    # assertion. The 20th slot goes to the strongest undated assertion.
    rows = [
        dict(edge(i, "Q1", f"Q{100+i}"), time_from="+1942-01-01T00:00:00Z")
        for i in range(19)
    ]
    rows += [edge(20, "Q1", "Q200"), edge(21, "Q1", "Q201")]
    rows += [
        dict(
            edge(22, "Q1", "Q252"),
            time_from="+1950-09-28T00:00:00Z",
            time_to="+1965-01-07T00:00:00Z",
        )
    ]
    # An out-of-period Event link is still uncapped and unfiltered.
    rows += [dict(edge(23, "Q1", "Q999"), time_point="+2000-01-01T00:00:00Z")]
    scores = {
        q: dict(score=1)
        for r in rows
        for q in (r["subject_entity_id"], r["object_entity_id"])
    }
    scores["Q200"]["score"], scores["Q201"]["score"] = 200, 100
    original = copy.deepcopy(rows)
    kept, audit = select(rows, scores, {"Q999"}, event_population_complete=True)
    assert {r["observation_id"] for r in kept} == {str(i) for i in range(19)} | {
        "20",
        "23",
    }
    assert rows == original
    assert audit[-2]["temporal_group"] == "OUTSIDE_PERIOD"
    assert audit[-1]["temporal_group"] == "EVENT_EXEMPT"
    # No tie between the dated tier and undated tier at their shared boundary.
    scores["Q200"]["score"] = 1
    rows = rows[:19] + [edge(20, "Q1", "Q200"), edge(21, "Q1", "Q201")]
    scores["Q201"]["score"] = 1
    with pytest.raises(SourceException, match="Unapproved importance tie") as error:
        select(rows, scores, set(), event_population_complete=True)
    assert error.value.case["temporal_group"] == "UNDATED"
    # Equal importance across different temporal tiers is not a cutoff tie.
    dated = rows[:19] + [
        dict(edge(30, "Q1", "Q200"), time_from="+1943-01-01T00:00:00Z")
    ]
    kept, _ = select(
        dated + [edge(31, "Q1", "Q201")], scores, set(), event_population_complete=True
    )
    assert kept == dated


def test_period_boundaries_points_open_intervals_and_partial_overlap():
    assert temporal_group(edge(1, "Q1", "Q2")) == "UNDATED"
    for day in ("1941-12-07", "1945-09-02"):
        assert (
            temporal_group(dict(edge(1, "Q1", "Q2"), time_point=f"+{day}T00:00:00Z"))
            == "IN_PERIOD"
        )
    for day in ("1941-12-06", "1945-09-03"):
        assert (
            temporal_group(dict(edge(1, "Q1", "Q2"), time_point=f"+{day}T00:00:00Z"))
            == "OUTSIDE_PERIOD"
        )
    assert (
        temporal_group(dict(edge(1, "Q1", "Q2"), time_to="+1942-00-00T00:00:00Z"))
        == "IN_PERIOD"
    )
    assert (
        temporal_group(dict(edge(1, "Q1", "Q2"), time_from="+1940-00-00T00:00:00Z"))
        == "IN_PERIOD"
    )
    for value, expected in (
        ("1945-00-00", "IN_PERIOD"),
        ("1941-00-00", "IN_PERIOD"),
        ("1945-09-00", "IN_PERIOD"),
        ("1941-12-00", "IN_PERIOD"),
        ("1940-00-00", "OUTSIDE_PERIOD"),
        ("1946-00-00", "OUTSIDE_PERIOD"),
        ("1945-10-00", "OUTSIDE_PERIOD"),
        ("1941-11-00", "OUTSIDE_PERIOD"),
    ):
        row = dict(edge(1, "Q1", "Q2"), time_point=f"+{value}T00:00:00Z")
        original = copy.deepcopy(row)
        assert temporal_group(row) == expected
        assert row == original
    for field, value in (("from", "1945"), ("to", "1941")):
        row = dict(
            edge(1, "Q1", "Q2"), **{f"time_{field}": f"+{value}-00-00T00:00:00Z"}
        )
        assert temporal_group(row) == "IN_PERIOD"
    # Approved year-only check; no Julian day conversion is added.
    julian = dict(
        edge(2, "Q1", "Q2"),
        time_point="-0207-00-00T00:00:00Z",
        attributes={
            "qualifiers": {
                "P585": [
                    {
                        "datavalue": {
                            "value": {
                                "calendarmodel": "http://www.wikidata.org/entity/Q1985786",
                                "time": "-0207-00-00T00:00:00Z",
                            }
                        }
                    }
                ]
            }
        },
    )
    assert temporal_group(julian) == "OUTSIDE_PERIOD"
    # An old Julian start with an open end can overlap the period.
    interval = copy.deepcopy(julian)
    interval["time_from"] = interval.pop("time_point")
    interval["attributes"]["qualifiers"]["P580"] = interval["attributes"][
        "qualifiers"
    ].pop("P585")
    assert temporal_group(interval) == "IN_PERIOD"
    julian["time_point"] = "+1945-09-02T00:00:00Z"
    julian["attributes"]["qualifiers"]["P585"][0]["datavalue"]["value"]["time"] = (
        julian["time_point"]
    )
    with pytest.raises(SourceException, match="Calendar requires"):
        temporal_group(julian)


def test_wikidata_precision_ranges_preserve_raw_dates_and_calendar_guard():
    for year, precision, expected in (
        (1950, 8, "OUTSIDE_PERIOD"),
        (1949, 8, "IN_PERIOD"),
        (1939, 8, "OUTSIDE_PERIOD"),
        (1900, 7, "OUTSIDE_PERIOD"),
        (1901, 7, "IN_PERIOD"),
        (2000, 7, "IN_PERIOD"),
        (2001, 7, "OUTSIDE_PERIOD"),
        (1000, 6, "OUTSIDE_PERIOD"),
        (1001, 6, "IN_PERIOD"),
        (2000, 6, "IN_PERIOD"),
        (2001, 6, "OUTSIDE_PERIOD"),
    ):
        row = dict(
            edge(1, "Q1", "Q2"),
            time_point=f"+{year:04d}-00-00T00:00:00Z",
            time_precision={"point": [precision]},
        )
        original = copy.deepcopy(row)
        assert temporal_group(row) == expected
        assert row == original
    row = dict(
        edge(2, "Q183", "Q948"),
        time_from="+1950-00-00T00:00:00Z",
        time_precision={"from": [8]},
    )
    assert temporal_group(row) == "OUTSIDE_PERIOD"
    row["time_from"] = "+1940-00-00T00:00:00Z"
    assert temporal_group(row) == "IN_PERIOD"
    row["attributes"] = {
        "qualifiers": {
            "P580": [
                {
                    "datavalue": {
                        "value": {
                            "time": row["time_from"],
                            "precision": 8,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985786",
                        }
                    }
                }
            ]
        }
    }
    # A Julian decade spanning the boundary years still needs interpretation.
    with pytest.raises(SourceException, match="Calendar requires"):
        temporal_group(row)

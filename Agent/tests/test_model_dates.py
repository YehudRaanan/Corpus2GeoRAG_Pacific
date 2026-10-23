"""Native scalar dates use precision/calendar from the unchanged data model."""

import gzip
import json

import pytest

from geo_agent.graph_store import Edge, GraphStore, Node
from geo_agent.model_dates import (
    GREGORIAN,
    JULIAN,
    in_range,
    event_dates,
    load_model_dates,
    relation_dates,
)


def native(value, precision=11, calendar=GREGORIAN):
    return {"time": value, "precision": precision, "calendarmodel": calendar}


@pytest.mark.parametrize(
    "precision,value,inside,outside",
    [
        (9, "+1945-00-00T00:00:00Z", "1945-09-02", "1946"),
        (10, "+1944-09-00T00:00:00Z", "1944-09-01", "1944-10"),
        (8, "+1940-00-00T00:00:00Z", "1949", "1950"),
        (7, "+1901-00-00T00:00:00Z", "2000", "2001"),
        (6, "+1001-00-00T00:00:00Z", "2000", "2001"),
    ],
)
def test_possible_overlap_preserves_source_precision(precision, value, inside, outside):
    metadata = {"point_date": native(value, precision)}
    original = json.dumps(metadata)
    assert in_range(metadata, inside, inside)
    assert not in_range(metadata, outside, outside)
    assert json.dumps(metadata) == original


def test_julian_shortcut_only_outside_project_period():
    old = {"point_date": native("+1507-01-01T00:00:00Z", calendar=JULIAN)}
    assert not in_range(old, "1941", "1945")
    with pytest.raises(ValueError, match="Calendar-sensitive"):
        in_range(old, "1507", "1507")
    with pytest.raises(ValueError, match="Calendar-sensitive"):
        in_range(old, "1941", None)
    boundary = {"point_date": native("+1941-12-07T00:00:00Z", calendar=JULIAN)}
    with pytest.raises(ValueError, match="Calendar-sensitive"):
        in_range(boundary, "1941", "1945")


def test_relation_floor_uses_selected_precision_and_original_calendar(tmp_path):
    selected = "+1900-00-00T00:00:00Z"
    row = {
        "observation_id": "one",
        "time_from": selected,
        "time_precision": '{"from":[11]}',
        "attributes": {
            "qualifiers": {
                "P580": [{"datavalue": {"value": native("+1776-07-04T00:00:00Z")}}]
            },
            "time_selection": {"decisions": {"from": {"selected_precision": [9]}}},
        },
    }
    dates = relation_dates(row)
    assert dates["start_date"]["precision"] == 9
    assert in_range(dates, "1942", "1942")  # Open end stays open.
    assert not in_range(dates, "1899", "1899")
    with gzip.open(tmp_path / "relations.json.gz", "wt", encoding="utf8") as stream:
        json.dump([row], stream)
    edges = [
        Edge(id="one", source="Q1", target="Q2", type="wd:P17", start_date=selected),
        Edge(
            id="reverse",
            source_edge_id="one",
            source="Q2",
            target="Q1",
            type="inverse:wd:P17",
            start_date=selected,
        ),
    ]
    loaded, _ = load_model_dates(tmp_path, {}, edges)
    assert loaded[id(edges[0])] == loaded[id(edges[1])] == dates
    edges[1].start_date = "+1901-00-00T00:00:00Z"
    with pytest.raises(ValueError, match="Graph/model relation date differs"):
        load_model_dates(tmp_path, {}, edges)


def test_undated_and_missing_interval_boundaries():
    assert not in_range({}, "1942", "1942")
    assert in_range({}, None, None)
    assert in_range({"end_date": native("+1942-01-01T00:00:00Z")}, "1941", "1941")
    assert not in_range({"end_date": native("+1942-01-01T00:00:00Z")}, "1943", "1943")


def test_event_native_dates_share_export_selection_and_model_join(tmp_path):
    start = "+1940-00-00T00:00:00Z"
    end = "+1945-09-00T00:00:00Z"
    row = {
        "event_id": "Q2",
        "start_date": [native(start, 9), native("+1942-01-01T00:00:00Z")],
        "end_date": [native(end, 10)],
    }
    dates = event_dates(row)
    assert dates["start_date"] == native(start, 9)
    assert dates["end_date"] == native(end, 10)
    with gzip.open(tmp_path / "events.json.gz", "wt", encoding="utf8") as stream:
        json.dump([row], stream)
    node = Node(
        id="Q2::event",
        wikidata_id="Q2",
        type="event",
        name="Event",
        attributes={"start_date": start, "end_date": end},
    )
    _, loaded = load_model_dates(tmp_path, {node.id: node}, [])
    store = GraphStore([node], [])
    store.model_node_dates = loaded
    assert store.model_event_in_range(node.id, "1945-09-02", "1945-09-02")
    assert not store.model_event_in_range(node.id, "1945-10", "1945-10")
    node.attributes["start_date"] = "+1941-00-00T00:00:00Z"
    with pytest.raises(ValueError, match="Graph/model Event date differs"):
        load_model_dates(tmp_path, {node.id: node}, [])


def test_native_event_year_context_requires_model_metadata():
    from geo_agent.agent import resolution_records
    from langchain_core.messages import HumanMessage, ToolMessage

    node = Node(
        id="Q2::event",
        wikidata_id="Q2",
        name="Battle",
        type="event",
        attributes={
            "start_date": "+1941-00-00T00:00:00Z",
            "end_date": "+1945-00-00T00:00:00Z",
        },
    )
    store = GraphStore([node], [])
    messages = [
        HumanMessage(content="Battle"),
        ToolMessage(
            name="search_entities",
            tool_call_id="search",
            content=json.dumps(store.search_entities("Battle")),
        ),
    ]
    assert resolution_records(store, [node.id], messages, "Battle")
    with pytest.raises(ValueError, match="model_dir"):
        resolution_records(store, [node.id], messages, "Battle in 1942")

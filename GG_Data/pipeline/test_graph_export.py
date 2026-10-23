"""Focused contract tests for model -> final graph; no source acquisition."""

from copy import deepcopy

import pytest

from GG_Data.pipeline.graph_export import build_graph, event_date_attributes


META = dict(
    schema_version="test",
    relation_map_version="relation-map-v2.1.2",
    release_status="TEST",
    scope="fixture",
)


def native(value: str, precision: int = 11, calendar: str = "Gregorian") -> dict:
    return dict(time=value, precision=precision, calendarmodel=calendar)


def fixture() -> dict:
    def entity(qid: str, kind: str) -> dict:
        return dict(
            entity_id=qid,
            type=kind,
            name=qid,
            aliases=[qid],
            sources=["kept in model"],
            geometry_ref={"not": "exported"},
        )

    mapping = dict(
        source="Wikidata",
        source_predicate="wd:P1",
        level2_relation_id="wd:P1",
        level2_relation_label="native relation",
        level1_family="UNRESOLVED",
        direction_to_level2="same",
        relation_map_version=META["relation_map_version"],
    )
    direction = dict(
        input_relation_id="wd:P1",
        output_reverse_relation_id="inverse:wd:P1",
        output_reverse_relation_label="inverse native relation",
        endpoint_action="SWAP_SOURCE_TARGET",
        direction_pair_id="pair1",
        relation_map_version=META["relation_map_version"],
    )
    row = dict(
        observation_id="obs-1",
        selected_source="Wikidata",
        selected_source_predicate="wd:P1",
        level2_relation="wd:P1",
        level2_label="native relation",
        level1_relation="UNRESOLVED",
        relation_map_version=META["relation_map_version"],
        subject_entity_id="Q1",
        object_entity_id="Q2",
        count=1,
        time_from="+1942-00-00T00:00:00Z",
        time_to="",
        time_point="",
    )
    return dict(
        entities=[
            entity("Q1", "LOC"),
            entity("Q1", "ORG"),
            entity("Q2", "event"),
            entity("SYN_sample", "LOC"),
            entity("SYN_bad_date", "DATE"),
        ],
        events=[
            dict(
                event_id="Q2",
                kind=[{"id": "Q123"}],
                start_date=[],
                end_date=[],
                point_date=[],
            )
        ],
        relations=[row],
        mapping=[mapping],
        directions=[direction],
        metadata=dict(META),
    )


def test_separate_typed_nodes_and_one_shared_assertion() -> None:
    source = fixture()
    original = deepcopy(source)
    graph, report = build_graph(**source)
    assert source == original
    assert [n["id"] for n in graph["nodes"]] == [
        "Q1::LOC",
        "Q1::ORG",
        "Q2::event",
        "SYN_sample",
    ]
    assert len(graph["edges"]) == 2  # No Cartesian product for Q1's two types.
    base, reverse = graph["edges"]
    assert (base["source"], base["target"], base["type"]) == ("Q1", "Q2", "wd:P1")
    assert (reverse["source"], reverse["target"], reverse["type"]) == (
        "Q2",
        "Q1",
        "inverse:wd:P1",
    )
    assert reverse["source_edge_id"] == base["id"]
    assert reverse["count"] == base["count"] == 1
    assert reverse["start_date"] == base["start_date"] == "+1942-00-00T00:00:00Z"
    assert graph["relation_catalog"][reverse["type"]]["source_predicates"] == []
    assert report["multi_type_qids"] == 1
    assert report["model_only_date_rows"] == 1
    assert all(
        not ({"geometry_ref", "geometry", "sources", "text", "embedding"} & n.keys())
        for n in graph["nodes"]
    )
    assert "attributes" not in graph["nodes"][2]  # No guessed kind from Q123.


def test_self_assertion_has_one_view_and_independent_assertions_stay_separate() -> None:
    source = fixture()
    row = source["relations"][0]
    source["relations"] += [
        dict(row, observation_id="obs-2"),
        dict(row, observation_id="obs-self", object_entity_id="Q1"),
    ]
    graph, report = build_graph(**source)
    assert len(graph["edges"]) == 5
    assert report["base_assertions"] == 3
    assert report["self_assertions"] == 1


def test_unapplied_provider_family_does_not_override_wikidata_rule() -> None:
    source = fixture()
    source["mapping"].append(
        dict(
            source["mapping"][0],
            source="EventKG",
            source_predicate="other:P1",
            level1_family="OTHER_FAMILY",
        )
    )
    graph, report = build_graph(**source)
    assert graph["relation_catalog"]["wd:P1"]["level1_families"] == ["UNRESOLVED"]
    assert (
        report["unused_provider_family_conflicts"][0]["unused_definitions"][0]["source"]
        == "EventKG"
    )


@pytest.mark.parametrize("other_family", ["UNRESOLVED", "CONFLICTING_ASSIGNED"])
def test_reverse_catalog_family_list_preserves_unassigned_edges(
    other_family: str,
) -> None:
    source = fixture()
    source["mapping"][0]["level1_family"] = "SPATIAL"
    source["relations"][0]["level1_relation"] = "SPATIAL"
    source["mapping"].append(
        dict(
            source["mapping"][0],
            source_predicate="inverse:wd:P1",
            level2_relation_id="inverse:wd:P1",
            level2_relation_label="inverse native relation",
            level1_family=other_family,
        )
    )
    source["directions"].append(
        dict(
            source["directions"][0],
            input_relation_id="inverse:wd:P1",
            output_reverse_relation_id="wd:P1",
            output_reverse_relation_label="native relation",
        )
    )
    source["relations"].append(
        dict(
            source["relations"][0],
            observation_id="obs-2",
            selected_source_predicate="inverse:wd:P1",
            level2_relation="inverse:wd:P1",
            level2_label="inverse native relation",
            level1_relation=other_family,
        )
    )
    if other_family != "UNRESOLVED":
        with pytest.raises(ValueError, match="Conflicting assigned catalog families"):
            build_graph(**source)
        return
    graph, report = build_graph(**source)
    assert all(
        d["level1_families"] == ["SPATIAL", "UNRESOLVED"]
        for d in graph["relation_catalog"].values()
    )
    assert [e["relation_family"] for e in graph["edges"]] == [
        "SPATIAL",
        "SPATIAL",
        "UNRESOLVED",
        "UNRESOLVED",
    ]
    assert len(report["unassigned_reverse_family_pairs"]) == 2


def test_event_minimum_start_maximum_end_and_originals_unchanged() -> None:
    event = dict(
        event_id="Q2",
        start_date=[native("+1897-04-28T00:00:00Z"), native("+1897-04-22T00:00:00Z")],
        end_date=[native("+1942-05-08T00:00:00Z"), native("+1942-05-10T00:00:00Z")],
        point_date=[native("+1941-00-00T00:00:00Z", 9)],
    )
    original = deepcopy(event)
    assert event_date_attributes(event) == dict(
        start_date="+1897-04-22T00:00:00Z",
        end_date="+1942-05-10T00:00:00Z",
        point_date="+1941-00-00T00:00:00Z",
    )
    assert event == original


def test_existing_multiple_point_range_is_reused_without_invented_point() -> None:
    values = [native("+1941-00-00T00:00:00Z", 9), native("+1945-00-00T00:00:00Z", 9)]
    event = dict(
        event_id="Q2",
        start_date=[values[0]],
        end_date=[values[1]],
        point_date=values,
        temporal_evidence=dict(derived_range={"from": {}, "to": {}}),
    )
    assert event_date_attributes(event) == dict(
        start_date=values[0]["time"], end_date=values[1]["time"]
    )
    event["temporal_evidence"] = {}
    event["start_date"] = []
    event["end_date"] = []
    with pytest.raises(ValueError, match="Unbounded multiple points"):
        event_date_attributes(event)


def test_mixed_calendars_do_not_trigger_unapproved_conversion() -> None:
    event = dict(
        event_id="Q2",
        start_date=[
            native("+1500-00-00T00:00:00Z", 9),
            native("+1501-00-00T00:00:00Z", 9, "Julian"),
        ],
    )
    with pytest.raises(ValueError, match="Mixed Event calendars"):
        event_date_attributes(event)


@pytest.mark.parametrize("bound", ["start_date", "end_date"])
def test_explicit_bound_and_multiple_points_keep_only_explicit_bound(
    bound: str,
) -> None:
    event = dict(
        event_id="Q2",
        point_date=[native("+1990-11-18T00:00:00Z"), native("+2019-05-04T00:00:00Z")],
        temporal_evidence=dict(derived_range={}),
    )
    event[bound] = [native("+1948-01-02T00:00:00Z")]
    original = deepcopy(event)
    assert event_date_attributes(event) == {bound: "+1948-01-02T00:00:00Z"}
    assert event == original


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda s: s["metadata"].pop("scope"), "Caller must supply"),
        (
            lambda s: s["relations"][0].update(object_entity_id="Q99"),
            "Unknown QID edge endpoint",
        ),
        (
            lambda s: s["mapping"][0].update(level1_family="CHANGED"),
            "Applied mapping differs",
        ),
        (
            lambda s: s["relations"].append(dict(s["relations"][0])),
            "Duplicate directional view ID",
        ),
        (
            lambda s: s["relations"][0].update(relation_map_version="other"),
            "mapping versions differ",
        ),
        (lambda s: s["entities"][0].update(name=""), "Missing entity name"),
        (lambda s: s["relations"][0].update(count=2), "Unexpected assertion count"),
    ],
)
def test_required_contract_failures(change, message: str) -> None:
    source = fixture()
    change(source)
    with pytest.raises(ValueError, match=message):
        build_graph(**source)

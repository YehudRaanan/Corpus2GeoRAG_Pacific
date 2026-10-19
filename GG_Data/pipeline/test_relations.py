"""Small source-gate check: population S2T 8, no network or Daniel outputs."""

from copy import deepcopy

import pytest

from GG_Data.pipeline.relations import SourceException, populate, scan, statement_time


def test_relation_scope_ranks_typed_rows_and_approved_multiple_start_dates():
    statement = dict(
        id="Q1$test",
        rank="deprecated",
        type="statement",
        mainsnak=dict(
            property="P2341",
            snaktype="value",
            datatype="wikibase-item",
            datavalue=dict(value={"entity-type": "item", "id": "Q2", "numeric-id": 2}),
        ),
    )
    entity = dict(
        entity_id="Q1",
        type="LOC",
        name="Example",
        sources=[],
        raw_reference={
            "full": {"entity": {"id": "Q1", "claims": {"P2341": [statement]}}}
        },
    )
    target = dict(
        entity_id="Q2",
        type="ORG",
        name="Target",
        sources=[],
        raw_reference={"full": {"entity": {"id": "Q2", "claims": {}}}},
    )
    other_type = {**entity, "type": "ORG"}
    original = deepcopy([entity, other_type, target])
    kept, excluded, counts = scan([entity, other_type, target], {"Q1", "Q2"}, {})
    assert len(kept) == 1 and not excluded
    assert kept[0]["raw_statement"] == statement
    assert counts["source_qids_checked"] == 2 and counts["rank.deprecated"] == 1
    assert [entity, other_type, target] == original
    mapping = {
        ("Wikidata", "wd:P2341"): dict(
            direction_to_level2="same",
            formal_component_conflict="True",
            level2_relation_id="wd:P2341",
            level2_decision="RETAIN_SOURCE_ID_BLOCK_FORMAL_TRANSLATION",
        )
    }
    assert len(scan([entity, target], {"Q1", "Q2"}, mapping)[0]) == 1
    mapping["Wikidata", "wd:P2341"]["level2_relation_id"] = "wd:P1"
    with pytest.raises(SourceException, match="Conflicting mapping"):
        scan([entity, target], {"Q1", "Q2"}, mapping)
    statement["qualifiers"] = {
        "P580": [
            {
                "datavalue": {
                    "value": {"time": "+1942-01-01T00:00:00Z", "precision": 11}
                }
            },
            {
                "datavalue": {
                    "value": {"time": "+1943-01-01T00:00:00Z", "precision": 11}
                }
            },
        ]
    }
    kept, _, _ = scan([entity, target], {"Q1", "Q2"}, {})
    assert kept[0]["raw_statement"] == statement
    assert kept[0]["time_status"] == "MULTIPLE"
    assert kept[0]["time_from"] == "+1942-01-01T00:00:00Z"

    # Approved scope: exclude only when the latest supplied end precedes 1900.
    def end(value):
        return {"datavalue": {"value": {"time": value, "precision": 9}}}

    statement["qualifiers"]["P582"] = [end("-0044-00-00T00:00:00Z")]
    kept, excluded, counts = scan([entity, target], {"Q1", "Q2"}, {})
    assert not kept and counts["excluded_ended_before_1900"] == 1
    assert excluded[0]["raw_statement"] == statement
    assert excluded[0]["reason"] == "ENDED_BEFORE_1900"
    statement["qualifiers"]["P582"].append(end("+1945-00-00T00:00:00Z"))
    assert len(scan([entity, target], {"Q1", "Q2"}, {})[0]) == 1
    del statement["qualifiers"]["P582"]
    assert len(scan([entity, target], {"Q1", "Q2"}, {})[0]) == 1


def test_date_floor_latest_end_and_unapproved_point_or_interval_conflicts():
    def snak(time, precision=11):
        return {"datavalue": {"value": {"time": time, "precision": precision}}}

    statement = {
        "qualifiers": {
            "P580": [snak("+1890-00-00T00:00:00Z", 9), snak("+1880-02-01T00:00:00Z")],
            "P582": [snak("+1940-01-01T00:00:00Z"), snak("+1945-09-02T00:00:00Z")],
        }
    }
    original = deepcopy(statement)
    time = statement_time(statement)
    assert time["time_from"] == "+1900-00-00T00:00:00Z"
    assert time["time_to"] == "+1945-09-02T00:00:00Z"
    assert time["time_selection"]["decisions"]["from"]["selected_precision"] == [9]
    assert time["time_selection"]["decisions"]["from"]["derived"] is True
    assert statement == original
    statement["qualifiers"]["P580"].append(snak("+1930-00-00T00:00:00Z", 9))
    assert statement_time(statement)["time_from"] == "+1930-00-00T00:00:00Z"
    statement["qualifiers"]["P582"] = [snak("+1920-00-00T00:00:00Z", 9)]
    assert statement_time(statement)["time_status"] == "CONFLICT"
    statement["qualifiers"]["P580"][0]["datavalue"]["value"]["time"] = "unknown"
    with pytest.raises(SourceException, match="Unsupported native date"):
        statement_time(statement)


def test_population_preserves_statement_identity_raw_dates_and_single_direction_swap():
    statement = dict(id="Q1$first", rank="normal", qualifiers={})
    case = dict(
        subject_qid="Q1",
        object_qid="Q2",
        source_predicate="wd:P361",
        source_record_id=statement["id"],
        raw_statement=statement,
        source_record=[],
        **statement_time(statement),
    )
    rule = dict(
        direction_to_level2="reverse",
        level1_family="UNRESOLVED",
        level1_assignment_status="NOT_ASSIGNED",
        level2_relation_id="wd:P527",
        level2_relation_label="has part",
        relation_map_version="relation-map-v2.1.2",
    )
    mapping = {("Wikidata", "wd:P361"): rule}
    original = deepcopy(case)
    row = populate([case], mapping)[0]
    assert case == original and row["input_assertion"]["raw_source"] == original
    assert (row["subject_entity_id"], row["object_entity_id"]) == ("Q2", "Q1")
    assert row["count"] == 1 and row["source_graph"] == ""
    assert len(row["input_assertion"]["legacy_fields"]) == 26
    assert row["final_review_status"] is None
    # A mapping direction/version change does not rewrite source assertion ID.
    rule["direction_to_level2"] = "same"
    assert populate([case], mapping)[0]["observation_id"] == row["observation_id"]
    second = deepcopy(case)
    second["source_record_id"] = second["raw_statement"]["id"] = "Q1$second"
    rows = populate([case, second], mapping)
    assert len({r["observation_id"] for r in rows}) == 2
    with pytest.raises(SourceException, match="Repeated base assertion"):
        populate([case, case], mapping)

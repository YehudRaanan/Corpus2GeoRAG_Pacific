"""Small native fixtures: retention and directed assertion identity."""

import pytest

from GG_Data.pipeline import post_qid_relations as api


def statement(subject="Q1", target="Q2", sid="a", prop="P17"):
    return {
        "id": subject + "$" + sid,
        "rank": "normal",
        "mainsnak": {
            "property": prop,
            "snaktype": "value",
            "datatype": "wikibase-item",
            "datavalue": {
                "value": {
                    "entity-type": "item",
                    "id": target,
                    "numeric-id": int(target[1:]),
                }
            },
        },
    }


def inputs():
    records = {q: {"id": q, "claims": {}} for q in ("Q1", "Q2")}
    records["Q1"]["claims"] = {"P17": [statement()]}
    entities = [
        {"entity_id": "Q1", "type": "MISC"},
        {"entity_id": "Q1", "type": "DATE"},
        {"entity_id": "Q2", "type": "LOC"},
    ]
    rule = dict(
        direction_to_level2="same",
        level1_family="UNRESOLVED",
        level1_assignment_status="NOT_ASSIGNED",
        level2_relation_id="wd:P17",
        level2_relation_label="country",
        relation_map_version="test",
        formal_component_conflict="False",
    )
    lookup = {
        "wd:P17": dict(
            output_reverse_relation_id="inverse:wd:P17",
            output_reverse_relation_label="country of",
            endpoint_action="SWAP_SOURCE_TARGET",
        ),
        "inverse:wd:P17": dict(
            output_reverse_relation_id="wd:P17",
            output_reverse_relation_label="country",
            endpoint_action="SWAP_SOURCE_TARGET",
        ),
    }
    return records, entities, {("Wikidata", "wd:P17"): rule}, lookup


def build(data):
    return api.build_relations(
        *data, sources={q: [{"file": "fixture"}] for q in data[0]}
    )


def test_native_assertion_has_two_linked_rows_without_typed_fanout():
    result = build(inputs())
    forward, reverse = result["relations"]
    assert (forward["subject_entity_id"], reverse["subject_entity_id"]) == ("Q1", "Q2")
    assert reverse["level2_relation"] == "inverse:wd:P17"
    assert reverse["observation_id"] == forward["observation_id"] + "::REVERSE"
    assert reverse["base_assertion_id"] == forward["observation_id"]
    assert reverse["source_edge_id"] == forward["observation_id"]
    assert reverse["selected_source_predicate"] == "wd:P17"
    assert result["counts"]["base_assertions"] == 1


def test_self_link_and_independent_reverse_remain_distinct():
    data = inputs()
    data[0]["Q1"]["claims"]["P17"].append(statement(target="Q1", sid="self"))
    data[0]["Q2"]["claims"] = {"P17": [statement("Q2", "Q1", "independent")]}
    result = build(data)
    assert len(result["relations"]) == 5
    assert result["counts"]["base_assertions"] == 3


def test_ambiguous_calendar_keeps_raw_assertion_and_empty_scalar_dates():
    data = inputs()
    raw = data[0]["Q1"]["claims"]["P17"][0]
    raw["qualifiers"] = {
        "P580": [
            {
                "datavalue": {
                    "value": {
                        "time": "+1800-00-00T00:00:00Z",
                        "precision": 9,
                        "calendarmodel": cal,
                    }
                }
            }
            for cal in ("gregorian", "julian")
        ]
    }
    result = build(data)
    row = result["relations"][0]
    assert row["time_status"] == "AMBIGUOUS"
    assert row["time_from"] is None
    assert row["input_assertion"]["raw_source"]["raw_statement"] == raw


def test_missing_record_and_corrupt_item_fail():
    data = inputs()
    del data[0]["Q2"]
    with pytest.raises(ValueError, match="Missing full"):
        build(data)
    data = inputs()
    data[0]["Q1"]["claims"]["P17"][0]["mainsnak"]["datavalue"]["value"][
        "numeric-id"
    ] = 3
    with pytest.raises(ValueError, match="native statement"):
        build(data)


def test_unknown_predicate_is_explicit_not_silently_lost():
    data = inputs()
    data[2].clear()
    data[0]["Q1"]["claims"]["P17"].append(statement(sid="second"))
    result = build(data)
    assert len(result["unknown_predicates"]) == 2
    assert result["status"] == "RELATIONS_READY"
    assert result["relations"][0]["level2_relation"] == "wd:P17"
    assert result["relations"][1]["level2_relation"] == "inverse:wd:P17"
    assert result["relations"][0]["mapping_origin"] == "native_identifier_preserved"


def test_event_selection_counts_distinct_corpus_neighbours_in_both_directions():
    records, entities, mapping, lookup = inputs()
    records["Q3"] = {
        "id": "Q3",
        "claims": {
            "P31": [statement("Q3", "Q1190554", prop="P31")],
            "P17": [statement("Q3", "Q2", "outgoing")],
        },
    }
    records["Q1"]["claims"]["P17"].append(statement("Q1", "Q3", "incoming"))
    chosen = api.select_events(records, {"Q1", "Q2"}, {"Q1190554"}, mapping)
    assert chosen["selected_event_qids"] == ["Q3"]
    assert chosen["decisions"][0]["linked_corpus_qids"] == ["Q1", "Q2"]
    assert (
        api.select_events(records, {"Q1"}, {"Q1190554"}, mapping)["selected_event_qids"]
        == []
    )


def test_all_exact_exclusions_are_guarded_and_do_not_suppress_other_assertions():
    from GG_Data.mapping.assertion_exclusions import load_exclusions

    exclusions = load_exclusions()
    assert len(exclusions) == 14
    for (source, sid), exclusion in exclusions.items():
        if source != "Wikidata":
            continue
        subject, target = exclusion["subject_qid"], exclusion["object_qid"]
        prop = exclusion["source_predicate"].removeprefix("wd:")
        raw = statement(subject, target, prop=prop)
        raw["id"] = sid
        records = {q: {"id": q, "claims": {}} for q in {subject, target}}
        records[subject]["claims"] = {prop: [raw]}
        rows = [{"entity_id": q} for q in records]
        result = build((records, rows, {}, {}))
        assert len(result["excluded"]) == 1
        assert result["relations"] == []
        raw["mainsnak"]["property"] = prop
        raw["mainsnak"]["datavalue"]["value"] = {
            "entity-type": "item",
            "id": "Q999999999",
            "numeric-id": 999999999,
        }
        records["Q999999999"] = {"id": "Q999999999", "claims": {}}
        with pytest.raises(ValueError, match="Excluded source record changed"):
            build((records, [{"entity_id": q} for q in records], {}, {}))


def test_degree_over_twenty_historical_dates_and_reverse_mapping_are_retained():
    data = inputs()
    data[2]["Wikidata", "wd:P17"]["direction_to_level2"] = "reverse"
    data[0]["Q1"]["claims"]["P17"] = [statement(sid=str(i)) for i in range(25)]
    result = build(data)
    assert len(result["relations"]) == 50
    assert result["relations"][0]["subject_entity_id"] == "Q2"
    assert result["relations"][1]["subject_entity_id"] == "Q1"


def test_identical_duplicate_retrieval_is_one_assertion():
    data = inputs()
    data[0]["Q1"]["claims"]["P17"].append(statement())
    result = build(data)
    assert len(result["relations"]) == 2
    assert result["counts"]["repeated_retrievals"] == 1


def test_export_stored_directions_once_with_independent_reverse_and_self():
    data = inputs()
    data[0]["Q1"]["claims"]["P17"].append(statement(target="Q1", sid="self"))
    data[0]["Q2"]["claims"] = {"P17": [statement("Q2", "Q1", "native_reverse")]}
    rows = build(data)["relations"]
    edges = api.export_stored_relations(rows)
    assert len(edges) == 5
    assert [e["id"] for e in edges] == [r["observation_id"] for r in rows]
    assert sum(e["source"] == e["target"] for e in edges) == 1
    assert {e["source_assertion_id"] for e in edges} == {
        "Q1$a",
        "Q1$self",
        "Q2$native_reverse",
    }
    assert edges[1]["type"] == "inverse:wd:P17"
    with pytest.raises(ValueError, match="Duplicate stored"):
        api.export_stored_relations(rows + rows[:1])

"""Small source-gate check: population S2T 8, no network or Daniel outputs."""

from copy import deepcopy

import pytest

from GG_Data.pipeline.relations import SourceException, scan


def test_relation_scope_ranks_typed_rows_and_stop_on_conflicting_dates():
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
    with pytest.raises(
        SourceException, match="Temporal values require consultation"
    ) as caught:
        scan([entity, target], {"Q1", "Q2"}, {})
    assert caught.value.case["raw_statement"] == statement
    assert caught.value.case["temporal_evidence"]["time_status"] == "MULTIPLE"

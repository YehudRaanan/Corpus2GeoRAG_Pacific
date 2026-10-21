"""Native Event dates and identities; population S2T 7, no source requests."""

from copy import deepcopy

from GG_Data.pipeline.event_model import event_rows


def test_event_dates_preserve_evidence_and_explicit_bounds():
    def statement(date):
        return {
            "mainsnak": {
                "datatype": "time",
                "datavalue": {
                    "value": {
                        "time": date,
                        "precision": 11,
                        "calendarmodel": "Gregorian",
                    }
                },
            }
        }

    record = {
        "id": "Q1",
        "labels": {"en": {"value": "Example"}},
        "claims": {
            "P585": [
                statement("+1945-08-09T00:00:00Z"),
                statement("+1945-08-06T00:00:00Z"),
            ]
        },
    }
    original = deepcopy(record)
    entity, event = event_rows(record, {"record_id": "Q1"}, {"keep_event": True})
    assert entity["entity_id"] == event["event_id"] == "Q1"
    assert entity["type"] == "event" and entity["attributes"]["mention_ids"] == []
    assert event["start_date"][0]["time"] == "+1945-08-06T00:00:00Z"
    assert event["end_date"][0]["time"] == "+1945-08-09T00:00:00Z"
    assert len(event["point_date"]) == 2
    assert event["temporal_evidence"]["derived_range"]["from"]["derived"]
    assert record == original
    record["claims"]["P580"] = [statement("+1944-01-01T00:00:00Z")]
    _, event = event_rows(record, {}, {})
    assert event["start_date"][0]["time"] == "+1944-01-01T00:00:00Z"
    assert event["end_date"] == []
    assert event["temporal_evidence"]["derived_range"] == {}

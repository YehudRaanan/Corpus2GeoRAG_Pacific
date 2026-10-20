"""Snapshot priority and complete same-ID fallback, without difference reports."""

import pytest

from GG_Data.pipeline.entities import choose_name, select_reference


def record(qid: str, revision: int, name: str) -> dict:
    return {
        "requested_qid": qid,
        "entity": {
            "id": qid,
            "lastrevid": revision,
            "claims": {},
            "labels": {"en": {"value": name}},
        },
    }


def test_snapshot_wins_over_newer_records_and_latest_fallback_wins_if_absent():
    pinned = (record("Q1", 1, "snapshot"), {"provider": "BIGQUERY"})
    older = (record("Q1", 2, "older"), {"provider": "WIKIDATA"})
    latest = (record("Q1", 3, "latest"), {"provider": "WIKIDATA"})
    assert select_reference("Q1", pinned, [latest]) == pinned
    assert select_reference("Q1", None, [latest, older]) == latest
    with pytest.raises(ValueError, match="No available"):
        select_reference("Q1", None, [])
    with pytest.raises(ValueError, match="differs"):
        select_reference("Q2", None, [latest])


def test_selected_record_supplies_name_without_comparing_other_versions():
    full = record("Q1", 1, "snapshot")["entity"]
    selected = choose_name("Q1", full, {"revision": 2, "labels": {"en": "newer"}}, [])
    assert selected["value"] == "snapshot"
    assert selected["source"] == "full_record"

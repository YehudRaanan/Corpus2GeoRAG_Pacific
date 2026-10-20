"""A changed source value must stop before any model update."""

import hashlib
import json

from GG_Data.pipeline import bq_full_alignment
from GG_Data.pipeline.bq_full_alignment import first_difference


def test_identity_difference_keeps_both_values_and_ignores_revision_only_changes():
    old = {"labels": {"en": {"value": "Romusha"}}, "lastrevid": 1}
    assert first_difference(old, {**old, "lastrevid": 2}) is None
    newer = {"labels": {"en": {"value": "rōmusha"}}, "lastrevid": 2}
    assert first_difference(old, newer) == {
        "field": "labels.en",
        "archived": {"value": "Romusha"},
        "pinned": {"value": "rōmusha"},
    }
    assert (
        first_difference(old, {**old, "claims": {"P31": [{"mainsnak": {}}]}})["field"]
        == "claims.P31"
    )


def test_approval_is_exact_and_does_not_hide_other_fields(monkeypatch):
    before = [{"mainsnak": {"value": "artillery model"}}]
    after = [{"mainsnak": {"value": "weapon model"}}]
    fingerprints = tuple(
        hashlib.sha256(
            json.dumps(v, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        for v in (before, after)
    )
    monkeypatch.setattr(bq_full_alignment, "APPROVED_Q1014037_P31", fingerprints)
    old, pinned = {"claims": {"P31": before}}, {"claims": {"P31": after}}
    assert first_difference(old, pinned, qid="Q1014037") is None
    assert first_difference(old, pinned, qid="Q2")["field"] == "claims.P31"
    assert first_difference(
        old, {"claims": {"P31": [{"mainsnak": {"value": "another"}}]}}, qid="Q1014037"
    )
    pinned["claims"]["P279"] = [{"mainsnak": {}}]
    assert first_difference(old, pinned, qid="Q1014037")["field"] == "claims.P279"


def test_optional_snak_hash_is_not_a_changed_fact_but_rank_is():
    statement = {
        "id": "Q1$statement",
        "rank": "normal",
        "mainsnak": {"value": "Q2", "property": "P31", "snaktype": "value"},
    }
    old = {
        "claims": {
            "P31": [
                {**statement, "mainsnak": {**statement["mainsnak"], "hash": "checksum"}}
            ]
        }
    }
    pinned = {"claims": {"P31": [statement]}}
    assert first_difference(old, pinned) is None
    assert "hash" in old["claims"]["P31"][0]["mainsnak"]
    statement["rank"] = "deprecated"
    assert first_difference(old, pinned)["field"] == "claims.P31"
    nested = {
        "references": [
            {
                "hash": "reference-id",
                "snaks": {
                    "P248": [
                        {
                            "property": "P248",
                            "snaktype": "value",
                            "hash": "optional",
                            "value": "Q3",
                        }
                    ]
                },
            }
        ]
    }
    cleaned = bq_full_alignment.without_snak_checksums(nested)
    assert cleaned["references"][0]["hash"] == "reference-id"
    assert cleaned["references"][0]["snaks"]["P248"] == [
        {"property": "P248", "snaktype": "value", "value": "Q3"}
    ]

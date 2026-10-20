"""A changed source value must stop before any model update."""

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
        first_difference(old, {**old, "claims": {"P31": ["changed"]}})["field"]
        == "claims.P31"
    )

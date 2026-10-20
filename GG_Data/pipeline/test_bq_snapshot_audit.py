"""Known BQ misses differ from unchecked and synthetic identities."""

import pytest

from GG_Data.pipeline.bq_snapshot_audit import availability


def test_only_explicit_pinned_bq_evidence_establishes_availability():
    assert availability("SYN_example", None) == "NOT_APPLICABLE_SYNTHETIC"
    assert availability("Q1", None) == "NOT_CHECKED"
    row = dict(id="Q1", reference_source="BIGQUERY", missing=False)
    assert availability("Q1", row) == "PRESENT_IN_PINNED_BQ"
    row["missing"] = True
    assert availability("Q1", row) == "MISSING_IN_PINNED_BQ"
    row["reference_source"] = "WIKIDATA"
    with pytest.raises(ValueError, match="Unverified"):
        availability("Q1", row)

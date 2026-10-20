"""Compact retrieval must preserve the measured selection and row denominator."""

import pytest

from GG_Data.pipeline.event_candidate_ids import ids_query, validate_ids
from GG_Data.pipeline.event_snapshot_discovery import measure_query


def test_projection_keeps_all_candidate_filters():
    measured = measure_query("`approved.snapshot`", {"Q1"}, {"Q2"})
    compact = ids_query(measured)
    assert compact.rsplit("\nSELECT", 1)[0] == measured.rsplit("\nSELECT", 1)[0]
    assert compact.endswith("SELECT id FROM candidates")
    assert "LIMIT" not in compact
    assert validate_ids([{"id": "Q2"}, {"id": "Q1"}], 2) == ["Q1", "Q2"]


@pytest.mark.parametrize(
    "rows,expected",
    [([{"id": "Q1"}], 2), ([{"id": "Q1"}, {"id": "Q1"}], 2), ([{"id": "SYN_1"}], 1)],
)
def test_incomplete_or_invalid_ids_stop(rows, expected):
    with pytest.raises(ValueError):
        validate_ids(rows, expected)

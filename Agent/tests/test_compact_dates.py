"""Date evidence is compared without inventing occurrence dates for edges."""

import pytest
from geo_agent.compact_dates import date_bounds, event_in_range, query_bounds


def native(value, precision=11, calendar="Q1985727"):
    return dict(
        time=value,
        precision=precision,
        calendarmodel="http://www.wikidata.org/entity/" + calendar,
    )


def test_julian_and_gregorian_and_partial_precision():
    assert date_bounds(
        native("+1941-12-07T00:00:00Z", calendar="Q1985786")
    ) == date_bounds(native("+1941-12-20T00:00:00Z"))
    lo, hi = date_bounds(native("+1944-02-00T00:00:00Z", 10))
    assert hi - lo == 28
    assert (
        date_bounds(native("+1901-00-00T00:00:00Z", 7))[0]
        == date_bounds(native("+1901-01-01T00:00:00Z"))[0]
    )
    assert (
        date_bounds(native("+1901-00-00T00:00:00Z", 7))[1]
        == date_bounds(native("+2000-12-31T00:00:00Z"))[1]
    )


def test_multiple_points_do_not_create_a_continuous_event():
    dates = {
        "point_date": [native("+1941-12-07T00:00:00Z"), native("+1945-08-15T00:00:00Z")]
    }
    assert event_in_range(dates, *query_bounds("1941", "1941"))
    assert not event_in_range(dates, *query_bounds("1943", "1943"))
    assert not event_in_range({}, *query_bounds("1941", "1945"))


def test_interval_overlap_and_invalid_queries():
    dates = {
        "start_date": [native("+1941-12-08T00:00:00Z")],
        "end_date": [native("+1941-12-10T00:00:00Z")],
    }
    assert event_in_range(dates, *query_bounds("1941-12-10", "1941-12-10"))
    assert not event_in_range(dates, *query_bounds(None, "1941-12-07"))
    for start, end in [("1941-02-30", None), ("1945", "1941"), ("today", None)]:
        with pytest.raises(ValueError):
            query_bounds(start, end)
    with pytest.raises(ValueError, match="calendar"):
        date_bounds(native("+1941-12-07T00:00:00Z", calendar="Q1"))


def test_independent_periods_do_not_bridge_gap():
    dates = {
        "periods": [
            {"point_date": [native("+1941-01-01T00:00:00Z")]},
            {"point_date": [native("+1945-01-01T00:00:00Z")]},
        ]
    }
    assert not event_in_range(dates, *query_bounds("1943", "1943"))


def test_point_evidence_is_checked_even_when_another_interval_does_not_match():
    dates = {
        "start_date": [native("+1941-01-01T00:00:00Z")],
        "end_date": [native("+1941-12-31T00:00:00Z")],
        "point_date": [native("+1945-08-15T00:00:00Z")],
    }
    assert event_in_range(dates, *query_bounds("1945", "1945"))
    assert not event_in_range(dates, *query_bounds("1943", "1943"))

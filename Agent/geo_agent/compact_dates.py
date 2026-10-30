"""Inclusive possible-overlap comparisons of native Event date evidence.

No dependency on the exporter is required in the portable Agent bundle.
Julian day arithmetic follows the Gregorian/Julian calendar rules described in
USNO, Explanatory Supplement chapter 15 (aa.usno.navy.mil/downloads/c15_usb_online.pdf).
Query dates use the proleptic Gregorian calendar; native calendars are preserved.
"""

from __future__ import annotations

import re

GREGORIAN = "http://www.wikidata.org/entity/Q1985727"
JULIAN = "http://www.wikidata.org/entity/Q1985786"
UNBOUNDED = 10**20


def _month_days(year: int, month: int, calendar: str) -> int:
    leap = year % 4 == 0 and (calendar == JULIAN or year % 100 != 0 or year % 400 == 0)
    return (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]


def _day(year: int, month: int, day: int, calendar: str) -> int:
    if not 1 <= month <= 12 or not 1 <= day <= _month_days(year, month, calendar):
        raise ValueError(f"Invalid date: {year}-{month}-{day}")
    a = (14 - month) // 12
    y, m = year + 4800 - a, month + 12 * a - 3
    result = day + (153 * m + 2) // 5 + 365 * y + y // 4
    return (
        result - y // 100 + y // 400 - 32045
        if calendar == GREGORIAN
        else result - 32083
    )


def date_bounds(value: dict) -> tuple[int, int]:
    calendar = value.get("calendarmodel")
    if calendar not in {GREGORIAN, JULIAN}:
        raise ValueError(f"Unsupported or unknown calendar: {calendar}")
    match = re.fullmatch(
        r"([+-]?\d+)-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}Z", value["time"]
    )
    if not match:
        raise ValueError("Invalid native time")
    year, month, day = map(int, match.groups())
    precision = value["precision"]
    if not isinstance(precision, int) or not 6 <= precision <= 14:
        raise ValueError(f"Unsupported date precision: {precision}")
    low_year = high_year = year
    if precision < 9:
        width = 10 ** (9 - precision)
        offset = 0 if precision == 8 else 1
        low_year = ((year - offset) // width) * width + offset
        high_year = low_year + width - 1
    low_month, high_month = (month, month) if precision >= 10 and month else (1, 12)
    low_day = day if precision >= 11 and month and day else 1
    high_day = (
        day
        if precision >= 11 and month and day
        else _month_days(high_year, high_month, calendar)
    )
    return _day(low_year, low_month, low_day, calendar), _day(
        high_year, high_month, high_day, calendar
    )


def query_bounds(date_from: str | None, date_to: str | None) -> tuple[int, int]:
    def parse(value: str | None, end: bool) -> int:
        if value is None:
            return UNBOUNDED if end else -UNBOUNDED
        match = re.fullmatch(r"([+-]?\d+)(?:-(\d{2}))?(?:-(\d{2}))?", value)
        if not match:
            raise ValueError(f"Invalid query date: {value}")
        y, m, d = match.groups()
        year = int(y)
        month = int(m) if m else (12 if end else 1)
        if not 1 <= month <= 12:
            raise ValueError(f"Invalid query month: {value}")
        day = int(d) if d else (_month_days(year, month, GREGORIAN) if end else 1)
        return _day(year, month, day, GREGORIAN)

    low, high = parse(date_from, False), parse(date_to, True)
    if low > high:
        raise ValueError("Query date range is reversed")
    return low, high


def event_in_range(dates: dict, low: int, high: int) -> bool:
    """Keep individual point dates separate; bounds are explicit source bounds."""
    if dates.get("periods") and any(
        event_in_range(period, low, high) for period in dates["periods"]
    ):
        return True
    starts = [date_bounds(v) for v in dates.get("start_date", [])]
    ends = [date_bounds(v) for v in dates.get("end_date", [])]
    if starts or ends:
        start = min(v[0] for v in starts) if starts else -UNBOUNDED
        end = max(v[1] for v in ends) if ends else UNBOUNDED
        if start > end:
            raise ValueError("Event source date range is reversed")
        if start <= high and end >= low:
            return True
    return any(
        a <= high and b >= low
        for a, b in (date_bounds(v) for v in dates.get("point_date", []))
    )

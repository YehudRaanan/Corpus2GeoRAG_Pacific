"""Population S2T 9.2: no invented exact selection dates."""

from GG_Data.pipeline.geography import selection_date, selection_value


def value(time, precision):
    return dict(time=time, precision=precision, source_id="saved-record")


def test_selection_date_preserves_partial_uncertainty():
    assert selection_date([], "Q1") == "1941-12-07"
    exact = value("+1942-03-04T00:00:00Z", 11)
    later = value("+1945-00-00T00:00:00Z", 9)
    assert selection_date([exact, later], "Q1") == "1942-03-04"
    outside = value("+1941-10-00T00:00:00Z", 10)
    assert selection_date([outside], "Q1") == "1941-12-07"
    assert selection_date([value("+1942-00-00T00:00:00Z", 9), exact], "Q1") == "1942"
    assert selection_date([later], "Q1") == "1945"
    assert selection_date([value("+1944-09-00T00:00:00Z", 10)], "Q1") == "1944-09"
    assert selection_value([value("+1940-00-00T00:00:00Z", 8)], "Q1") == dict(
        selection_date="1940", selection_precision=8
    )

from datetime import date, datetime, timedelta, timezone

import pytest

from app import analysis
from app.data import Dataset

UTC = timezone.utc


def dt(*a):
    return datetime(*a, tzinfo=UTC)


def make_ds():
    """Two half-hours of delivery day 2026-01-10; decision cutoff is 2026-01-09 09:00 UTC (GMT in Jan)."""
    s1, s2 = dt(2026, 1, 10, 0, 0), dt(2026, 1, 10, 0, 30)
    forecasts = {
        s1: ([dt(2026, 1, 9, 6), dt(2026, 1, 9, 8), dt(2026, 1, 9, 10)], [100.0, 200.0, 999.0]),
        s2: ([dt(2026, 1, 9, 10)], [500.0]),  # only published after cutoff -> unavailable
    }
    actuals = {s1: 150.0, s2: 400.0}
    return Dataset(actuals=actuals, forecasts=forecasts, source="test"), s1, s2


def test_cutoff_is_day_before_in_london_time():
    assert analysis.cutoff_utc(date(2026, 1, 10), "09:00") == dt(2026, 1, 9, 9)


def test_latest_forecast_respects_cutoff():
    ds, s1, s2 = make_ds()
    cutoff = analysis.cutoff_utc(date(2026, 1, 10), "09:00")
    assert analysis.latest_forecast(ds, s1, cutoff) == (dt(2026, 1, 9, 8), 200.0)  # not the 10:00 one
    assert analysis.latest_forecast(ds, s2, cutoff) is None


def test_day_rows_error_sign_and_missing():
    ds, s1, s2 = make_ds()
    rows = analysis.day_ahead_rows(ds, date(2026, 1, 10), "09:00")
    assert rows[0]["forecast"] == 200.0 and rows[0]["error"] == 50.0  # over-forecast is positive
    assert rows[1]["forecast"] is None and rows[1]["error"] is None
    assert len(rows) == 48


def test_metrics_known_values():
    m = analysis.metrics([(110, 100), (90, 100), (130, 100), (100, 100)])
    # errors: +10, -10, +30, 0
    assert m["n"] == 4
    assert m["mae"] == pytest.approx(12.5)
    assert m["bias"] == pytest.approx(7.5)
    assert m["rmse"] == pytest.approx(((100 + 100 + 900) / 4) ** 0.5)
    assert m["buffer_p90"] == pytest.approx(analysis.percentile([-10, 0, 10, 30], 90))


def test_metrics_empty_is_none():
    assert analysis.metrics([]) is None


def test_buffer_never_negative():
    assert analysis.metrics([(50, 100), (60, 100)])["buffer_p90"] == 0.0


def test_percentile_interpolates():
    assert analysis.percentile([0, 10], 50) == 5
    assert analysis.percentile([1, 2, 3, 4, 5], 100) == 5


def test_delivery_days_window():
    days = analysis.delivery_days()
    assert days[0] == date(2026, 1, 2) and days[-1] == date(2026, 2, 1) and len(days) == 31


def test_horizon_buckets():
    ds, s1, _ = make_ds()
    # s1 (00:00) forecasts published 06/08/10h on Jan 9 -> horizons 18h, 16h, 14h;
    # s2 (00:30) published 10h -> 14.5h. Buckets: [12,18) holds 16h, 14h, 14.5h; [18,24) holds 18h.
    res = analysis.horizon_summary(ds)
    b = {x["fromHours"]: x for x in res["buckets"]}
    assert b[12]["metrics"]["n"] == 3 and b[18]["metrics"]["n"] == 1

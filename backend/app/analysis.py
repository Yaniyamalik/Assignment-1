"""Forecast selection and accuracy analysis. Pure functions, no I/O.

Domain assumptions (also documented in the README):
* A purchase decision made on day D-1 is for delivery day D (London calendar day).
* At decision time the buyer only has forecasts with publishTime <= cutoff, so for
  every half-hour we use the LATEST forecast published at or before the cutoff.
* "Decisions in January 2026" => decision dates 2026-01-01..2026-01-31, i.e. delivery
  days 2026-01-02..2026-02-01.
* Error = forecast - actual. Positive error = over-forecast = the buyer is short of
  power and must cover the gap (e.g. from thermal plant / intraday market).
"""
from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .data import Dataset

LONDON = ZoneInfo("Europe/London")
DECISION_START = date(2026, 1, 1)
DECISION_END = date(2026, 1, 31)
DEFAULT_CUTOFF = "09:00"  # London time on D-1; configurable per request
HALF_HOUR = timedelta(minutes=30)


def parse_cutoff(cutoff: str) -> tuple[int, int]:
    hh, mm = cutoff.split(":")
    h, m = int(hh), int(mm)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("cutoff must be HH:MM")
    return h, m


def cutoff_utc(delivery_date: date, cutoff: str) -> datetime:
    h, m = parse_cutoff(cutoff)
    d = delivery_date - timedelta(days=1)
    return datetime(d.year, d.month, d.day, h, m, tzinfo=LONDON).astimezone(timezone.utc)


def delivery_days() -> list[date]:
    n = (DECISION_END - DECISION_START).days + 1
    return [DECISION_START + timedelta(days=i + 1) for i in range(n)]


def day_slots(delivery_date: date) -> list[datetime]:
    start = datetime(delivery_date.year, delivery_date.month, delivery_date.day, tzinfo=LONDON)
    end = start + timedelta(days=1)
    s, e = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    out, t = [], s
    while t < e:
        out.append(t)
        t += HALF_HOUR
    return out


def latest_forecast(ds: Dataset, start: datetime, as_of: datetime):
    """Latest forecast for target `start` published at or before `as_of`, or None."""
    entry = ds.forecasts.get(start)
    if not entry:
        return None
    pubs, vals = entry
    i = bisect_right(pubs, as_of)
    if i == 0:
        return None
    return pubs[i - 1], vals[i - 1]


def day_ahead_rows(ds: Dataset, delivery_date: date, cutoff: str) -> list[dict]:
    as_of = cutoff_utc(delivery_date, cutoff)
    rows = []
    for start in day_slots(delivery_date):
        lf = latest_forecast(ds, start, as_of)
        actual = ds.actuals.get(start)
        row = {
            "startTime": start.isoformat().replace("+00:00", "Z"),
            "forecast": lf[1] if lf else None,
            "publishTime": lf[0].isoformat().replace("+00:00", "Z") if lf else None,
            "actual": actual,
            "error": (lf[1] - actual) if (lf and actual is not None) else None,
        }
        rows.append(row)
    return rows


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        raise ValueError("empty")
    k = (len(sorted_vals) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def metrics(pairs: list[tuple[float, float]]) -> dict | None:
    """pairs = (forecast, actual). Returns None if there is nothing to score."""
    if not pairs:
        return None
    errs = [f - a for f, a in pairs]
    n = len(errs)
    abs_sorted = sorted(abs(e) for e in errs)
    err_sorted = sorted(errs)
    mean_actual = sum(a for _, a in pairs) / n
    mae = sum(abs_sorted) / n
    return {
        "n": n,
        "mae": mae,
        "rmse": math.sqrt(sum(e * e for e in errs) / n),
        "bias": sum(errs) / n,
        "p50_abs_error": percentile(abs_sorted, 50),
        "p90_abs_error": percentile(abs_sorted, 90),
        # MW by which the actual fell short of forecast in 90% / 95% of half-hours.
        "buffer_p90": max(0.0, percentile(err_sorted, 90)),
        "buffer_p95": max(0.0, percentile(err_sorted, 95)),
        "mean_actual": mean_actual,
        "nmae_pct": (mae / mean_actual * 100) if mean_actual > 0 else None,
    }


def _scored(rows: list[dict]) -> list[tuple[float, float]]:
    return [(r["forecast"], r["actual"]) for r in rows if r["error"] is not None]


def day_summary(ds: Dataset, delivery_date: date, cutoff: str) -> dict:
    rows = day_ahead_rows(ds, delivery_date, cutoff)
    return {
        "deliveryDate": delivery_date.isoformat(),
        "decisionDate": (delivery_date - timedelta(days=1)).isoformat(),
        "cutoffUtc": cutoff_utc(delivery_date, cutoff).isoformat().replace("+00:00", "Z"),
        "rows": rows,
        "metrics": metrics(_scored(rows)),
        "coverage": {
            "slots": len(rows),
            "withForecast": sum(r["forecast"] is not None for r in rows),
            "withActual": sum(r["actual"] is not None for r in rows),
        },
    }


def accuracy_summary(ds: Dataset, cutoff: str, bin_mw: int = 1000) -> dict:
    all_pairs: list[tuple[float, float]] = []
    daily, by_hour = [], defaultdict(list)
    for d in delivery_days():
        rows = day_ahead_rows(ds, d, cutoff)
        pairs = _scored(rows)
        all_pairs.extend(pairs)
        daily.append({"deliveryDate": d.isoformat(), "metrics": metrics(pairs)})
        for r in rows:
            if r["error"] is not None:
                hour = datetime.fromisoformat(r["startTime"].replace("Z", "+00:00")).astimezone(LONDON).hour
                by_hour[hour].append((r["forecast"], r["actual"]))
    hourly = [{"hour": h, "metrics": metrics(by_hour[h])} for h in sorted(by_hour)]

    hist: dict[int, int] = defaultdict(int)
    for f, a in all_pairs:
        hist[math.floor((f - a) / bin_mw)] += 1
    histogram = [
        {"from": b * bin_mw, "to": (b + 1) * bin_mw, "count": hist[b]} for b in sorted(hist)
    ]
    return {
        "cutoff": cutoff,
        "overall": metrics(all_pairs),
        "daily": daily,
        "hourly": hourly,
        "histogram": histogram,
    }


def horizon_summary(ds: Dataset, bucket_hours: int = 6, max_hours: int = 96) -> dict:
    """Accuracy as a function of forecast lead time (target start - publishTime).

    Uses every forecast published during January 2026 whose target has an actual.
    """
    lo = datetime(2026, 1, 1, tzinfo=timezone.utc)
    hi = datetime(2026, 2, 1, tzinfo=timezone.utc)
    buckets: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for start, (pubs, vals) in ds.forecasts.items():
        actual = ds.actuals.get(start)
        if actual is None:
            continue
        for p, v in zip(pubs, vals):
            if not (lo <= p < hi):
                continue
            h = (start - p).total_seconds() / 3600
            if 0 <= h < max_hours:
                buckets[int(h // bucket_hours) * bucket_hours].append((v, actual))
    return {
        "bucketHours": bucket_hours,
        "buckets": [
            {"fromHours": b, "toHours": b + bucket_hours, "metrics": metrics(buckets[b])}
            for b in sorted(buckets)
        ],
    }

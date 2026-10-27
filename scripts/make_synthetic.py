#!/usr/bin/env python3
"""Generate SYNTHETIC data with the same schema as the Elexon CSVs.

For local development / CI only, when you cannot reach the Elexon API. The numbers are
made up (smooth random wind + forecast noise that grows with lead time) and the app shows
a banner whenever data/DATA_SOURCE.txt says "synthetic".
"""
from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data"
CAPACITY = 17000.0
random.seed(42)

t0 = datetime(2025, 12, 27, tzinfo=timezone.utc)
t_end = datetime(2026, 2, 3, tzinfo=timezone.utc)
step = timedelta(minutes=30)

# Latent "true" wind: AR(1) on a 30-min grid plus a slow daily wobble.
actual: dict[datetime, float] = {}
x, t = 0.45, t0
while t < t_end:
    x = 0.985 * x + 0.015 * 0.45 + random.gauss(0, 0.012)
    x = min(max(x, 0.02), 0.97)
    wobble = 0.03 * math.sin(2 * math.pi * (t.hour + t.minute / 60) / 24)
    actual[t] = round(min(max((x + wobble) * CAPACITY, 0), CAPACITY), 1)
    t += step

OUT.mkdir(exist_ok=True)
with open(OUT / "actuals.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["startTime", "settlementDate", "settlementPeriod", "fuelType", "generation"])
    for start, gen in actual.items():
        if datetime(2026, 1, 1, tzinfo=timezone.utc) <= start < datetime(2026, 2, 2, tzinfo=timezone.utc):
            sp = (start.hour * 60 + start.minute) // 30 + 1
            w.writerow([start.strftime("%Y-%m-%dT%H:%M:%SZ"), start.date().isoformat(), sp, "WIND", gen])

n_rows = 0
with open(OUT / "forecasts.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["publishTime", "startTime", "generation"])
    pub = datetime(2025, 12, 29, tzinfo=timezone.utc)
    while pub < datetime(2026, 2, 1, tzinfo=timezone.utc):
        for k in range(0, 144):  # targets 0..72h ahead
            start = pub + k * step
            if start not in actual:
                continue
            h = k / 2
            sigma = 250 + 110 * math.sqrt(h)
            val = actual[start] - 120 + random.gauss(0, sigma)
            val = round(min(max(val, 0), CAPACITY), 1)
            w.writerow([pub.strftime("%Y-%m-%dT%H:%M:%SZ"), start.strftime("%Y-%m-%dT%H:%M:%SZ"), val])
            n_rows += 1
        pub += timedelta(hours=3)

(OUT / "DATA_SOURCE.txt").write_text("synthetic\n")
print(f"synthetic data written to {OUT} ({len(actual)} actual points, {n_rows} forecast rows)")

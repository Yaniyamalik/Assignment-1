#!/usr/bin/env python3
"""Download Jan 2026 wind actuals (FUELHH) and forecasts (WINDFOR) from Elexon BMRS into data/*.csv.

Run this once on a machine with internet access, then commit the CSVs so the deployed app
does not depend on the live API:

    python scripts/fetch_elexon.py

Standard library only. NOTE: endpoint parameter names follow the public BMRS v1 API docs
(https://bmrs.elexon.co.uk/api-documentation); if Elexon changes them, adjust the two URL
builders below.
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = Path(__file__).resolve().parents[1] / "data"

# Decisions are made on 2026-01-01..2026-01-31 for delivery 2026-01-02..2026-02-01.
ACTUALS_FROM, ACTUALS_TO = date(2026, 1, 1), date(2026, 2, 1)
# Forecasts published from a couple of days earlier so the first decision day has history.
PUBLISH_FROM, PUBLISH_TO = datetime(2025, 12, 29, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc)


def get_json(url: str, retries: int = 4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            return payload["data"] if isinstance(payload, dict) and "data" in payload else payload
        except Exception as exc:  # noqa: BLE001 - retry on any transient failure
            if attempt == retries - 1:
                raise
            print(f"  retry after error: {exc}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_actuals() -> list[dict]:
    rows, d = [], ACTUALS_FROM
    while d <= ACTUALS_TO:
        end = min(d + timedelta(days=6), ACTUALS_TO)
        q = urllib.parse.urlencode(
            {"settlementDateFrom": d.isoformat(), "settlementDateTo": end.isoformat(), "fuelType": "WIND"}
        )
        print(f"FUELHH {d} -> {end}")
        rows += [r for r in get_json(f"{BASE}/FUELHH/stream?{q}") if r.get("fuelType") == "WIND"]
        d = end + timedelta(days=1)
    return rows


def fetch_forecasts() -> list[dict]:
    rows, t = [], PUBLISH_FROM
    while t < PUBLISH_TO:
        end = min(t + timedelta(days=1), PUBLISH_TO)
        q = urllib.parse.urlencode({"publishDateTimeFrom": iso(t), "publishDateTimeTo": iso(end)})
        print(f"WINDFOR published {t:%Y-%m-%d}")
        rows += get_json(f"{BASE}/WINDFOR/stream?{q}")
        t = end
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {path}")


def main():
    OUT.mkdir(exist_ok=True)
    actuals, forecasts = fetch_actuals(), fetch_forecasts()
    if not actuals or not forecasts:
        sys.exit("Got no rows back - check the API parameters / your network.")
    write_csv(OUT / "actuals.csv", ["startTime", "settlementDate", "settlementPeriod", "fuelType", "generation"], actuals)
    write_csv(OUT / "forecasts.csv", ["publishTime", "startTime", "generation"], forecasts)
    (OUT / "DATA_SOURCE.txt").write_text("elexon\n")


if __name__ == "__main__":
    main()

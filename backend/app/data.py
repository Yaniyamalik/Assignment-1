"""Data loading: CSV files produced by scripts/fetch_elexon.py (or the synthetic generator)."""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (Elexon uses a trailing Z) into an aware UTC datetime."""
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class Dataset:
    # target startTime -> actual wind MW (FUELHH, fuelType == WIND)
    actuals: dict[datetime, float]
    # target startTime -> parallel lists (publish times ascending, MW) (WINDFOR)
    forecasts: dict[datetime, tuple[list[datetime], list[float]]]
    source: str  # "elexon" or "synthetic"


def load_dataset(data_dir: Path = DATA_DIR) -> Dataset:
    actuals: dict[datetime, float] = {}
    with open(data_dir / "actuals.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("fuelType", "WIND") != "WIND":
                continue
            actuals[parse_ts(row["startTime"])] = float(row["generation"])

    raw: dict[datetime, dict[datetime, float]] = {}
    with open(data_dir / "forecasts.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            start = parse_ts(row["startTime"])
            raw.setdefault(start, {})[parse_ts(row["publishTime"])] = float(row["generation"])

    forecasts = {}
    for start, by_pub in raw.items():
        pubs = sorted(by_pub)
        forecasts[start] = (pubs, [by_pub[p] for p in pubs])

    source_file = data_dir / "DATA_SOURCE.txt"
    source = source_file.read_text().strip().lower() if source_file.exists() else "elexon"
    return Dataset(actuals=actuals, forecasts=forecasts, source=source)


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    return load_dataset()

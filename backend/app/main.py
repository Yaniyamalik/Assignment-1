from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import analysis
from .data import get_dataset

app = FastAPI(title="Wind Forecast Monitor", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def _cutoff(value: str) -> str:
    try:
        analysis.parse_cutoff(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="cutoff must be HH:MM (London time, day before delivery)")
    return value


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    ds = get_dataset()
    days = analysis.delivery_days()
    return {
        "dataSource": ds.source,
        "defaultCutoff": analysis.DEFAULT_CUTOFF,
        "deliveryDays": [d.isoformat() for d in days],
        "actualPoints": len(ds.actuals),
        "forecastTargets": len(ds.forecasts),
    }


@app.get("/api/decision/{delivery_date}")
def decision(delivery_date: date, cutoff: str = Query(analysis.DEFAULT_CUTOFF)):
    """Forecast available at decision time for one delivery day, vs what actually happened."""
    if delivery_date not in analysis.delivery_days():
        raise HTTPException(status_code=404, detail="delivery date outside the January 2026 decision window")
    return analysis.day_summary(get_dataset(), delivery_date, _cutoff(cutoff))


@app.get("/api/accuracy")
def accuracy(cutoff: str = Query(analysis.DEFAULT_CUTOFF)):
    return analysis.accuracy_summary(get_dataset(), _cutoff(cutoff))


@app.get("/api/horizon")
def horizon():
    return analysis.horizon_summary(get_dataset())

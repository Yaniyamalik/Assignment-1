import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta_lists_31_delivery_days():
    r = client.get("/api/meta").json()
    assert len(r["deliveryDays"]) == 31 and r["deliveryDays"][0] == "2026-01-02"


def test_decision_ok_and_bad_inputs():
    ok = client.get("/api/decision/2026-01-15?cutoff=09:00")
    assert ok.status_code == 200 and len(ok.json()["rows"]) == 48
    assert client.get("/api/decision/2026-03-01").status_code == 404
    assert client.get("/api/decision/2026-01-15?cutoff=25:99").status_code == 422
    assert client.get("/api/decision/2026-01-15?cutoff=banana").status_code == 422


def test_accuracy_and_horizon_shapes():
    acc = client.get("/api/accuracy").json()
    assert acc["overall"]["n"] > 0 and len(acc["daily"]) == 31
    hz = client.get("/api/horizon").json()
    assert hz["buckets"][0]["fromHours"] == 0

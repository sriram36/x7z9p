from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.tests.test_analysis import DAYS, make_store


@pytest.fixture()
def client():
    main.set_store(make_store())
    yield TestClient(main.app)
    main.set_store(None)


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["ready"] and body["delivery_days"][0] == "2026-01-02"


def test_meta_without_data():
    main.set_store(None)
    body = TestClient(main.app).get("/api/meta").json()
    assert body["ready"] is False
    assert TestClient(main.app).get("/api/accuracy").status_code == 503


def test_forecast_day(client):
    body = client.get("/api/forecast", params={"day": "2026-01-04", "cutoff": "09:00"}).json()
    assert len(body["slots"]) == 48
    assert body["cutoff_utc"] == "2026-01-03T09:00:00Z"
    first = body["slots"][0]
    assert first["forecast_mw"] == 1100.0 and first["actual_mw"] == 1000.0 and first["error_mw"] == 100.0
    assert body["summary"]["forecast_gwh"] == 26.4  # 1100 MW * 24 h
    assert first["band_lo_mw"] == 1000.0


def test_forecast_validation(client):
    assert client.get("/api/forecast", params={"day": "2026-02-20"}).status_code == 404
    assert client.get("/api/forecast", params={"day": "2026-01-04", "cutoff": "9am"}).status_code == 422


def test_accuracy_and_horizon(client):
    acc = client.get("/api/accuracy").json()
    assert acc["overall"]["n"] == 48 * len(DAYS)
    hor = client.get("/api/horizon", params={"start": "2026-01-02", "end": "2026-01-03"}).json()
    assert hor["buckets"]
    assert client.get("/api/accuracy", params={"start": "2026-01-05", "end": "2026-01-02"}).status_code == 400

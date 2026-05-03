import json

import pytest
from pymongo.errors import PyMongoError

from app import db as db_module
from app.main import create_app, get_app, _serialize_room


@pytest.fixture
def client(seeded_db):
    app = create_app(db_override=seeded_db)
    app.testing = True
    return app.test_client()


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "service": "recommendation"}


def test_list_rooms_endpoint(client):
    resp = client.get("/api/rooms")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "rooms" in data
    assert len(data["rooms"]) == 2
    # _id is renamed to room_id and stringified.
    assert all("room_id" in r for r in data["rooms"])
    assert all("_id" not in r for r in data["rooms"])


def test_recommend_endpoint_returns_ranked_rooms(client):
    resp = client.get("/api/recommend")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["algorithm"] == "weighted"
    assert len(data["recommendations"]) == 2
    # r1 has empty/quiet live data, so it should outrank the packed/loud r2.
    assert data["recommendations"][0]["room_id"] == "r1"
    assert "study_score" in data["recommendations"][0]


def test_recommend_endpoint_respects_top_param(client):
    resp = client.get("/api/recommend?top=1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["recommendations"]) == 1


def test_recommend_endpoint_respects_live_weight(client):
    resp = client.get("/api/recommend?live_weight=0.0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["live_weight"] == 0.0


def test_recommend_endpoint_rejects_bad_live_weight(client):
    resp = client.get("/api/recommend?live_weight=not-a-number")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_recommend_endpoint_rejects_bad_top(client):
    resp = client.get("/api/recommend?top=abc")
    assert resp.status_code == 400


def test_forecast_endpoint_uses_now_when_no_target(client):
    resp = client.get("/api/forecast")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["algorithm"] == "forecast"
    assert "target_weekday" in data
    assert "target_hour" in data


def test_forecast_endpoint_with_explicit_target(client):
    resp = client.get("/api/forecast?weekday=2&hour=14&top=1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["target_weekday"] == 2
    assert data["target_hour"] == 14
    assert len(data["recommendations"]) == 1


def test_forecast_endpoint_validates_weekday_range(client):
    resp = client.get("/api/forecast?weekday=9")
    assert resp.status_code == 400


def test_forecast_endpoint_validates_hour_range(client):
    resp = client.get("/api/forecast?hour=99")
    assert resp.status_code == 400


def test_recommend_endpoint_handles_db_errors(monkeypatch, client):
    def _boom(*_a, **_kw):
        raise PyMongoError("simulated outage")

    monkeypatch.setattr(db_module, "list_rooms", _boom)
    resp = client.get("/api/recommend")
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "database_error"


def test_forecast_endpoint_handles_db_errors(monkeypatch, client):
    def _boom(*_a, **_kw):
        raise PyMongoError("simulated outage")

    monkeypatch.setattr(db_module, "list_rooms", _boom)
    resp = client.get("/api/forecast")
    assert resp.status_code == 503


def test_list_rooms_endpoint_handles_db_errors(monkeypatch, client):
    def _boom(*_a, **_kw):
        raise PyMongoError("simulated outage")

    monkeypatch.setattr(db_module, "list_rooms", _boom)
    resp = client.get("/api/rooms")
    assert resp.status_code == 503


def test_serialize_room_handles_datetimes_and_objectid_like():
    from datetime import datetime, timezone
    room = {
        "_id": "abc123",
        "name": "Test",
        "last_updated": datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
        "current_crowd": 3,
    }
    out = _serialize_room(room)
    assert out["room_id"] == "abc123"
    assert "_id" not in out
    assert out["last_updated"] == "2024-06-01T12:00:00+00:00"
    assert out["current_crowd"] == 3


def test_get_app_creates_singleton(monkeypatch):
    """Smoke test that the gunicorn entry helper creates an app once."""
    # Replace the module-level cache to ensure a fresh creation.
    import app.main as main_module
    monkeypatch.setattr(main_module, "app", None)
    monkeypatch.setattr(main_module, "create_app", lambda: "stub-app")
    assert main_module.get_app() == "stub-app"
    # Second call should return the same object without recreating.
    monkeypatch.setattr(main_module, "create_app", lambda: "different-app")
    assert main_module.get_app() == "stub-app"

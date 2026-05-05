from datetime import datetime, timezone

from pymongo.errors import PyMongoError

from app import db as db_module
from app.main import _serialize_room


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "service": "recommendation"}


def test_list_rooms_endpoint(seeded):
    resp = seeded.get("/api/rooms")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["rooms"]) == 2
    assert all("room_id" in r for r in data["rooms"])
    assert all("_id" not in r for r in data["rooms"])


def test_recommend_returns_ranked(seeded):
    resp = seeded.get("/api/recommend")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["algorithm"] == "weighted"
    assert len(data["recommendations"]) == 2
    assert data["recommendations"][0]["room_id"] == "r1"


def test_recommend_respects_top(seeded):
    resp = seeded.get("/api/recommend?top=1")
    assert resp.status_code == 200
    assert len(resp.get_json()["recommendations"]) == 1


def test_recommend_respects_live_weight(seeded):
    resp = seeded.get("/api/recommend?live_weight=0.0")
    assert resp.status_code == 200
    assert resp.get_json()["live_weight"] == 0.0


def test_recommend_rejects_bad_live_weight(seeded):
    resp = seeded.get("/api/recommend?live_weight=abc")
    assert resp.status_code == 400


def test_recommend_rejects_bad_top(seeded):
    resp = seeded.get("/api/recommend?top=abc")
    assert resp.status_code == 400


def test_forecast_default_uses_now(seeded):
    resp = seeded.get("/api/forecast")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "target_weekday" in data
    assert "target_hour" in data


def test_forecast_explicit_target(seeded):
    resp = seeded.get("/api/forecast?weekday=2&hour=14&top=1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["target_weekday"] == 2
    assert data["target_hour"] == 14
    assert len(data["recommendations"]) == 1


def test_forecast_validates_weekday(seeded):
    resp = seeded.get("/api/forecast?weekday=9")
    assert resp.status_code == 400


def test_forecast_validates_hour(seeded):
    resp = seeded.get("/api/forecast?hour=99")
    assert resp.status_code == 400


def test_recommend_handles_db_error(monkeypatch, seeded):
    def boom(*_a, **_kw):
        raise PyMongoError("simulated outage")
    monkeypatch.setattr(db_module, "list_rooms", boom)
    resp = seeded.get("/api/recommend")
    assert resp.status_code == 503


def test_forecast_handles_db_error(monkeypatch, seeded):
    def boom(*_a, **_kw):
        raise PyMongoError("simulated outage")
    monkeypatch.setattr(db_module, "list_rooms", boom)
    resp = seeded.get("/api/forecast")
    assert resp.status_code == 503


def test_list_rooms_handles_db_error(monkeypatch, seeded):
    def boom(*_a, **_kw):
        raise PyMongoError("simulated outage")
    monkeypatch.setattr(db_module, "list_rooms", boom)
    resp = seeded.get("/api/rooms")
    assert resp.status_code == 503


def test_serialize_room_handles_datetime():
    out = _serialize_room({
        "_id": "abc",
        "name": "Test",
        "last_updated": datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
        "current_crowd": 3,
    })
    assert out["room_id"] == "abc"
    assert "_id" not in out
    assert out["last_updated"] == "2024-06-01T12:00:00+00:00"
    assert out["current_crowd"] == 3

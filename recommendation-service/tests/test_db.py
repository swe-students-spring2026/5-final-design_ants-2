"""Unit tests for the database access layer."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app import db as db_module


def test_recent_checkins_filters_by_window(seeded_db):
    docs = db_module.recent_checkins(seeded_db, minutes=30)
    # Only the live checkins (5 minutes old) should match.
    assert len(docs) == 3


def test_recent_checkins_filters_by_room(seeded_db):
    docs = db_module.recent_checkins(seeded_db, room_id="r1", minutes=30)
    assert all(d["room_id"] == "r1" for d in docs)
    assert len(docs) == 2


def test_recent_checkins_uses_default_window(seeded_db):
    """Calling without `minutes` should fall back to Config.LIVE_WINDOW_MINUTES."""
    docs = db_module.recent_checkins(seeded_db)
    assert len(docs) == 3  # same as the explicit 30


def test_historical_checkins_returns_all_when_unfiltered(seeded_db):
    docs = db_module.historical_checkins(seeded_db)
    assert len(docs) == 6  # everything in the seeded DB


def test_historical_checkins_filters_by_room(seeded_db):
    docs = db_module.historical_checkins(seeded_db, room_id="r2")
    assert all(d["room_id"] == "r2" for d in docs)


def test_historical_checkins_filters_by_weekday_and_hour(seeded_db, now_utc):
    """Filter by weekday/hour matching one of our seeded entries' timestamps."""
    target = now_utc - timedelta(minutes=5)
    docs = db_module.historical_checkins(
        seeded_db, weekday=target.weekday(), hour=target.hour
    )
    # All three live checkins were inserted at this moment; depending on the
    # second they might cross an hour boundary, so we assert "at least one".
    assert len(docs) >= 1


def test_historical_checkins_skips_invalid_time(seeded_db):
    seeded_db["checkins"].insert_many(
        [{"_id": "bad", "room_id": "r1", "time": "not a datetime",
          "crowdedness": 1, "quietness": 1}]
    )
    docs = db_module.historical_checkins(seeded_db, weekday=0, hour=0)
    assert all(isinstance(d.get("time"), datetime) for d in docs)


def test_list_rooms_and_get_room(seeded_db):
    rooms = db_module.list_rooms(seeded_db)
    assert len(rooms) == 2

    one = db_module.get_room(seeded_db, "r1")
    assert one is not None
    assert one["name"] == "BBST 5F"

    missing = db_module.get_room(seeded_db, "does-not-exist")
    assert missing is None


def test_get_client_caches_instance():
    """Two calls without a reset should return the same client object."""
    db_module._client = None
    with patch("app.db.MongoClient") as mock_client:
        mock_client.return_value = "fake-client"
        c1 = db_module.get_client("mongodb://x")
        c2 = db_module.get_client("mongodb://x")
        assert c1 is c2
        # MongoClient should have been constructed only once.
        assert mock_client.call_count == 1
    # Bypass close() since the cached value is a plain string.
    db_module._client = None


def test_reset_client_closes_existing(monkeypatch):
    db_module._client = None

    closed = {"count": 0}

    class DummyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def close(self):
            closed["count"] += 1

        def __getitem__(self, _name):
            return {}

    monkeypatch.setattr(db_module, "MongoClient", DummyClient)
    db_module.get_client("mongodb://x")
    db_module.reset_client()
    assert closed["count"] == 1


def test_get_db_returns_named_database(monkeypatch):
    db_module._client = None

    class DummyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __getitem__(self, name):
            return f"db:{name}"

        def close(self):
            pass

    monkeypatch.setattr(db_module, "MongoClient", DummyClient)
    assert db_module.get_db(uri="mongodb://x", db_name="custom") == "db:custom"
    db_module.reset_client()

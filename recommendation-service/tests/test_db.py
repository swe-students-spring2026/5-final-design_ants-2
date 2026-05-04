"""Unit tests for the database access layer."""
from datetime import datetime, timedelta, timezone

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



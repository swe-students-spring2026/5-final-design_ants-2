from datetime import datetime, timedelta

import pytest

from app.db import (
    checkins_collection,
    get_room,
    historical_checkins,
    list_rooms,
    parse_time,
    recent_checkins,
    rooms_collection,
)


@pytest.fixture(autouse=True)
def clean_db():
    rooms_collection.delete_many({})
    checkins_collection.delete_many({})
    yield
    rooms_collection.delete_many({})
    checkins_collection.delete_many({})


def _seed():
    rooms_collection.insert_many([
        {"_id": "r1", "name": "Room 1"},
        {"_id": "r2", "name": "Room 2"},
    ])
    now = datetime.utcnow()
    live = (now - timedelta(minutes=5)).isoformat()
    old = (now - timedelta(days=3)).isoformat()
    checkins_collection.insert_many([
        {"user_id": "u1", "room_id": "r1", "time": live, "crowdedness": 2, "quietness": 5},
        {"user_id": "u2", "room_id": "r1", "time": live, "crowdedness": 1, "quietness": 4},
        {"user_id": "u3", "room_id": "r2", "time": live, "crowdedness": 5, "quietness": 1},
        {"user_id": "u1", "room_id": "r1", "time": old, "crowdedness": 3, "quietness": 3},
    ])


def test_list_rooms_returns_all():
    _seed()
    assert len(list_rooms()) == 2


def test_get_room_by_id():
    _seed()
    r = get_room("r1")
    assert r is not None
    assert r["name"] == "Room 1"
    assert get_room("missing") is None


def test_recent_checkins_filters_window():
    _seed()
    docs = recent_checkins(minutes=30)
    assert len(docs) == 3


def test_recent_checkins_filters_by_room():
    _seed()
    docs = recent_checkins(room_id="r1", minutes=30)
    assert all(d["room_id"] == "r1" for d in docs)
    assert len(docs) == 2


def test_recent_checkins_default_window():
    _seed()
    assert len(recent_checkins()) == 3


def test_historical_checkins_returns_all():
    _seed()
    assert len(historical_checkins()) == 4


def test_historical_checkins_filters_by_room():
    _seed()
    docs = historical_checkins(room_id="r2")
    assert all(d["room_id"] == "r2" for d in docs)


def test_historical_checkins_filters_by_weekday_hour():
    _seed()
    now = datetime.utcnow()
    docs = historical_checkins(weekday=now.weekday(), hour=now.hour)
    assert all(d["time"].startswith(now.strftime("%Y-%m-%d")) for d in docs)


def test_historical_checkins_skips_invalid_time():
    rooms_collection.insert_many([{"_id": "r1", "name": "Room 1"}])
    checkins_collection.insert_many([
        {"user_id": "u1", "room_id": "r1", "time": "not-a-datetime",
         "crowdedness": 1, "quietness": 1}
    ])
    docs = historical_checkins(weekday=0, hour=0)
    assert docs == []


def test_parse_time_handles_string_datetime_and_garbage():
    assert parse_time("2024-01-01T10:00:00") == datetime(2024, 1, 1, 10, 0, 0)
    assert parse_time(datetime(2024, 1, 1)) == datetime(2024, 1, 1)
    assert parse_time("not-a-time") is None
    assert parse_time(None) is None
    assert parse_time(12345) is None

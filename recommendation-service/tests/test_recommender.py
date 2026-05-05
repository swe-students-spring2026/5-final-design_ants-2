from datetime import datetime, timedelta

import pytest

from app.config import Config
from app.recommender import (
    forecast_score,
    rank_rooms_forecast,
    rank_rooms_weighted,
    weighted_score,
)


def _checkin_at(weekday, hour, crowd, quiet):
    base = datetime(2024, 1, 1)
    delta_days = (weekday - base.weekday()) % 7
    t = base + timedelta(days=delta_days, hours=hour)
    return {"time": t.isoformat(), "crowdedness": crowd, "quietness": quiet}


def test_weighted_score_uses_live_only_when_no_history():
    room = {"_id": "r1", "name": "Room"}
    live = [{"crowdedness": 2, "quietness": 5}, {"crowdedness": 2, "quietness": 5}]
    out = weighted_score(room, live, [])
    assert out["source"] == "live"
    assert out["crowd"] == 2.0
    assert out["quiet"] == 5.0


def test_weighted_score_uses_history_only_when_no_live():
    room = {"_id": "r1", "name": "Room"}
    hist = [{"crowdedness": 4, "quietness": 2}]
    out = weighted_score(room, [], hist)
    assert out["source"] == "history"
    assert out["crowd"] == 4.0


def test_weighted_score_blends_when_both_present():
    room = {"_id": "r1", "name": "Room"}
    live = [{"crowdedness": 1, "quietness": 5}]
    hist = [{"crowdedness": 5, "quietness": 1}]
    out = weighted_score(room, live, hist, live_weight=0.5)
    assert out["source"] == "live+history"
    assert out["crowd"] == 3.0
    assert out["quiet"] == 3.0


def test_weighted_score_falls_back_to_defaults():
    room = {"_id": "r1", "name": "Room"}
    out = weighted_score(room, [], [])
    assert out["source"] == "default"
    assert out["crowd"] == Config.DEFAULT_CROWD


def test_weighted_score_clamps_weights_outside_range():
    room = {"_id": "r1", "name": "Room"}
    live = [{"crowdedness": 1, "quietness": 5}]
    hist = [{"crowdedness": 5, "quietness": 1}]
    high = weighted_score(room, live, hist, live_weight=5.0)
    assert high["crowd"] == 1.0
    low = weighted_score(room, live, hist, live_weight=-2.0)
    assert low["crowd"] == 5.0


def test_rank_rooms_weighted_orders_best_first():
    rooms = [{"_id": "a", "name": "A"}, {"_id": "b", "name": "B"}]
    live_by_room = {
        "a": [{"crowdedness": 5, "quietness": 1}],
        "b": [{"crowdedness": 1, "quietness": 5}],
    }
    history_by_room = {"a": [], "b": []}
    ranked = rank_rooms_weighted(rooms, live_by_room, history_by_room)
    assert ranked[0]["room_id"] == "b"


def test_forecast_score_uses_exact_bucket():
    room = {"_id": "r1", "name": "Room"}
    history = [
        _checkin_at(2, 14, 1, 5),
        _checkin_at(2, 14, 1, 5),
        _checkin_at(2, 14, 1, 5),
        _checkin_at(0, 9, 5, 1),
    ]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    assert out["basis"] == "exact_bucket"
    assert out["sample_size"] == 3


def test_forecast_score_widens_to_same_hour():
    room = {"_id": "r1", "name": "Room"}
    history = [
        _checkin_at(2, 14, 2, 4),
        _checkin_at(3, 14, 2, 4),
        _checkin_at(4, 14, 2, 4),
    ]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    assert out["basis"] == "same_hour"


def test_forecast_score_falls_back_to_all_history():
    room = {"_id": "r1", "name": "Room"}
    history = [_checkin_at(0, 9, 3, 3), _checkin_at(1, 10, 3, 3)]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    assert out["basis"] == "all_history"


def test_forecast_score_falls_back_to_defaults():
    room = {"_id": "r1", "name": "Room"}
    out = forecast_score(room, [], target_weekday=2, target_hour=14)
    assert out["basis"] == "default"
    assert out["crowd"] == Config.DEFAULT_CROWD


def test_forecast_score_skips_invalid_time():
    room = {"_id": "r1", "name": "Room"}
    history = [
        {"time": "not-a-datetime", "crowdedness": 1, "quietness": 5},
        _checkin_at(2, 14, 1, 5),
    ]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    assert out["basis"] == "all_history"


def test_rank_rooms_forecast_with_explicit_target():
    rooms = [{"_id": "a", "name": "A"}, {"_id": "b", "name": "B"}]
    history_by_room = {
        "a": [_checkin_at(2, 14, 5, 1)] * 3,
        "b": [_checkin_at(2, 14, 1, 5)] * 3,
    }
    ranked = rank_rooms_forecast(rooms, history_by_room, target_weekday=2, target_hour=14)
    assert ranked[0]["room_id"] == "b"


def test_rank_rooms_forecast_defaults_to_now():
    rooms = [{"_id": "a", "name": "A"}]
    ranked = rank_rooms_forecast(rooms, {"a": []})
    now = datetime.utcnow()
    assert ranked[0]["target_weekday"] == now.weekday()
    assert ranked[0]["target_hour"] == now.hour

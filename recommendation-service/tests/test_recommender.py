"""Unit tests for the recommendation algorithms."""
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Config
from app.recommender import (
    _bucket_key,
    _study_score,
    forecast_score,
    rank_rooms_forecast,
    rank_rooms_weighted,
    weighted_score,
)


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

def test_study_score_combines_crowd_and_quiet():
    # crowd=1 (empty) and quiet=5 (silent) is the ideal study spot.
    assert _study_score(1, 5) == 10.0
    # crowd=5 (packed) and quiet=1 (loud) is the worst.
    assert _study_score(5, 1) == 2.0
    # Symmetry around the middle.
    assert _study_score(3, 3) == 6.0


def test_bucket_key_returns_weekday_and_hour():
    # 2024-01-01 was a Monday.
    t = datetime(2024, 1, 1, 14, 30, tzinfo=timezone.utc)
    assert _bucket_key(t) == (0, 14)


# ---------------------------------------------------------------------------
# Algorithm 1: weighted_score
# ---------------------------------------------------------------------------

def test_weighted_score_uses_live_only_when_no_history():
    room = {"_id": "r1", "name": "Room"}
    live = [{"crowdedness": 2, "quietness": 5}, {"crowdedness": 2, "quietness": 5}]
    out = weighted_score(room, live, [])
    assert out["source"] == "live"
    assert out["crowd"] == 2.0
    assert out["quiet"] == 5.0
    assert out["live_sample_size"] == 2
    assert out["history_sample_size"] == 0


def test_weighted_score_uses_history_only_when_no_live():
    room = {"_id": "r1", "name": "Room"}
    hist = [{"crowdedness": 4, "quietness": 2}]
    out = weighted_score(room, [], hist)
    assert out["source"] == "history"
    assert out["crowd"] == 4.0
    assert out["quiet"] == 2.0


def test_weighted_score_blends_when_both_present():
    room = {"_id": "r1", "name": "Room"}
    live = [{"crowdedness": 1, "quietness": 5}]
    hist = [{"crowdedness": 5, "quietness": 1}]
    out = weighted_score(room, live, hist, live_weight=0.5)
    assert out["source"] == "live+history"
    # 0.5 * 1 + 0.5 * 5 = 3.0
    assert out["crowd"] == 3.0
    assert out["quiet"] == 3.0


def test_weighted_score_falls_back_to_defaults():
    room = {"_id": "r1", "name": "Room"}
    out = weighted_score(room, [], [])
    assert out["source"] == "default"
    assert out["crowd"] == Config.DEFAULT_CROWD
    assert out["quiet"] == Config.DEFAULT_QUIET


def test_weighted_score_clamps_weights_outside_range():
    room = {"_id": "r1", "name": "Room"}
    live = [{"crowdedness": 1, "quietness": 5}]
    hist = [{"crowdedness": 5, "quietness": 1}]

    # Above 1 should clamp to 1: result equals pure live.
    high = weighted_score(room, live, hist, live_weight=5.0)
    assert high["crowd"] == 1.0 and high["quiet"] == 5.0

    # Below 0 should clamp to 0: result equals pure history.
    low = weighted_score(room, live, hist, live_weight=-2.0)
    assert low["crowd"] == 5.0 and low["quiet"] == 1.0


def test_weighted_score_handles_partial_fields():
    """A checkin missing one of the two fields should not crash and should
    contribute only to the field it has."""
    room = {"_id": "r1", "name": "Room"}
    live = [{"crowdedness": 1}, {"quietness": 5}]
    out = weighted_score(room, live, [])
    assert out["crowd"] == 1.0
    assert out["quiet"] == 5.0


def test_rank_rooms_weighted_orders_best_first():
    rooms = [
        {"_id": "a", "name": "A"},
        {"_id": "b", "name": "B"},
    ]
    live_by_room = {
        "a": [{"crowdedness": 5, "quietness": 1}],  # bad
        "b": [{"crowdedness": 1, "quietness": 5}],  # good
    }
    history_by_room = {"a": [], "b": []}
    ranked = rank_rooms_weighted(rooms, live_by_room, history_by_room)
    assert ranked[0]["room_id"] == "b"
    assert ranked[1]["room_id"] == "a"


# ---------------------------------------------------------------------------
# Algorithm 2: forecast_score
# ---------------------------------------------------------------------------

def _checkin_at(weekday: int, hour: int, crowd: float, quiet: float):
    """Build a checkin whose time has the requested weekday and hour."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)  # Monday
    delta_days = (weekday - base.weekday()) % 7
    t = base + timedelta(days=delta_days, hours=hour)
    return {"time": t, "crowdedness": crowd, "quietness": quiet}


def test_forecast_score_uses_exact_bucket_when_enough_samples():
    room = {"_id": "r1", "name": "Room"}
    history = [
        _checkin_at(2, 14, 1, 5),  # Wed 2pm, three of them
        _checkin_at(2, 14, 1, 5),
        _checkin_at(2, 14, 1, 5),
        _checkin_at(0, 9, 5, 1),   # Mon 9am, noise
    ]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    assert out["basis"] == "exact_bucket"
    assert out["crowd"] == 1.0
    assert out["quiet"] == 5.0
    assert out["sample_size"] == 3


def test_forecast_score_widens_to_same_hour_if_few_exact():
    room = {"_id": "r1", "name": "Room"}
    history = [
        _checkin_at(2, 14, 2, 4),
        _checkin_at(3, 14, 2, 4),
        _checkin_at(4, 14, 2, 4),
    ]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    assert out["basis"] == "same_hour"
    assert out["sample_size"] == 3


def test_forecast_score_falls_back_to_all_history():
    room = {"_id": "r1", "name": "Room"}
    history = [_checkin_at(0, 9, 3, 3), _checkin_at(1, 10, 3, 3)]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    assert out["basis"] == "all_history"
    assert out["sample_size"] == 2


def test_forecast_score_falls_back_to_defaults_when_empty():
    room = {"_id": "r1", "name": "Room"}
    out = forecast_score(room, [], target_weekday=2, target_hour=14)
    assert out["basis"] == "default"
    assert out["crowd"] == Config.DEFAULT_CROWD


def test_forecast_score_skips_checkins_with_invalid_time():
    room = {"_id": "r1", "name": "Room"}
    history = [
        {"time": "not-a-datetime", "crowdedness": 1, "quietness": 5},
        _checkin_at(2, 14, 1, 5),
    ]
    out = forecast_score(room, history, target_weekday=2, target_hour=14)
    # Only one valid sample at exact bucket; not enough for "exact_bucket"
    # (requires >= 3), so should fall back to all_history.
    assert out["basis"] == "all_history"


def test_rank_rooms_forecast_with_explicit_target():
    rooms = [{"_id": "a", "name": "A"}, {"_id": "b", "name": "B"}]
    history_by_room = {
        "a": [_checkin_at(2, 14, 5, 1)] * 3,  # bad on Wed 2pm
        "b": [_checkin_at(2, 14, 1, 5)] * 3,  # good on Wed 2pm
    }
    ranked = rank_rooms_forecast(rooms, history_by_room, target_weekday=2, target_hour=14)
    assert ranked[0]["room_id"] == "b"


def test_rank_rooms_forecast_defaults_to_now():
    """When no target is passed, it should still produce a valid response."""
    rooms = [{"_id": "a", "name": "A"}]
    ranked = rank_rooms_forecast(rooms, {"a": []})
    assert len(ranked) == 1
    now = datetime.now(timezone.utc)
    assert ranked[0]["target_weekday"] == now.weekday()
    assert ranked[0]["target_hour"] == now.hour

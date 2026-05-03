from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from .config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _avg(values: List[float], default: float) -> float:
    return float(mean(values)) if values else float(default)


def _study_score(crowd: float, quiet: float) -> float:
    spaciousness = 6.0 - crowd
    return round(spaciousness + quiet, 2)


# ---------------------------------------------------------------------------
# Algorithm 1: simple weighted score
# ---------------------------------------------------------------------------

def weighted_score(
    room: Dict[str, Any],
    live_checkins: List[Dict[str, Any]],
    historical_checkins: List[Dict[str, Any]],
    live_weight: Optional[float] = None,
) -> Dict[str, Any]:
    """Score a single room by blending live and historical signal.

    If there is no live data, the score falls back fully to history.
    If there is no history either, we use the configured defaults so that
    the room is still rankable rather than dropped.
    """
    w = Config.LIVE_WEIGHT if live_weight is None else float(live_weight)
    w = max(0.0, min(1.0, w))

    live_crowd_vals = [c["crowdedness"] for c in live_checkins if "crowdedness" in c]
    live_quiet_vals = [c["quietness"] for c in live_checkins if "quietness" in c]

    hist_crowd_vals = [c["crowdedness"] for c in historical_checkins if "crowdedness" in c]
    hist_quiet_vals = [c["quietness"] for c in historical_checkins if "quietness" in c]

    has_live = bool(live_crowd_vals or live_quiet_vals)
    has_hist = bool(hist_crowd_vals or hist_quiet_vals)

    if has_live and has_hist:
        crowd = w * _avg(live_crowd_vals, Config.DEFAULT_CROWD) + \
                (1 - w) * _avg(hist_crowd_vals, Config.DEFAULT_CROWD)
        quiet = w * _avg(live_quiet_vals, Config.DEFAULT_QUIET) + \
                (1 - w) * _avg(hist_quiet_vals, Config.DEFAULT_QUIET)
        source = "live+history"
    elif has_live:
        crowd = _avg(live_crowd_vals, Config.DEFAULT_CROWD)
        quiet = _avg(live_quiet_vals, Config.DEFAULT_QUIET)
        source = "live"
    elif has_hist:
        crowd = _avg(hist_crowd_vals, Config.DEFAULT_CROWD)
        quiet = _avg(hist_quiet_vals, Config.DEFAULT_QUIET)
        source = "history"
    else:
        crowd = Config.DEFAULT_CROWD
        quiet = Config.DEFAULT_QUIET
        source = "default"

    return {
        "room_id": str(room.get("_id")),
        "name": room.get("name"),
        "crowd": round(crowd, 2),
        "quiet": round(quiet, 2),
        "study_score": _study_score(crowd, quiet),
        "source": source,
        "live_sample_size": len(live_crowd_vals),
        "history_sample_size": len(hist_crowd_vals),
    }


def rank_rooms_weighted(
    rooms: List[Dict[str, Any]],
    live_by_room: Dict[Any, List[Dict[str, Any]]],
    history_by_room: Dict[Any, List[Dict[str, Any]]],
    live_weight: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Score and rank a list of rooms, best for studying first."""
    scored = [
        weighted_score(
            r,
            live_by_room.get(r["_id"], []),
            history_by_room.get(r["_id"], []),
            live_weight=live_weight,
        )
        for r in rooms
    ]
    scored.sort(key=lambda x: x["study_score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Algorithm 2: weekday/hour bucket forecast
# ---------------------------------------------------------------------------

def _bucket_key(t: datetime) -> Tuple[int, int]:
    return (t.weekday(), t.hour)


def forecast_score(
    room: Dict[str, Any],
    historical_checkins: List[Dict[str, Any]],
    target_weekday: int,
    target_hour: int,
) -> Dict[str, Any]:
    """Predict the score for ``room`` at the given (weekday, hour) slot.

    Strategy:
      1. Prefer checkins matching exactly (weekday, hour).
      2. If too few samples, widen to same hour on any weekday.
      3. If still empty, fall back to all historical data for the room.
      4. If still empty, fall back to defaults.
    """
    exact: List[Dict[str, Any]] = []
    same_hour: List[Dict[str, Any]] = []

    for c in historical_checkins:
        t = c.get("time")
        if not isinstance(t, datetime):
            continue
        wd, hr = _bucket_key(t)
        if hr == target_hour:
            same_hour.append(c)
            if wd == target_weekday:
                exact.append(c)

    if len(exact) >= 3:
        chosen, basis = exact, "exact_bucket"
    elif len(same_hour) >= 3:
        chosen, basis = same_hour, "same_hour"
    elif historical_checkins:
        chosen, basis = historical_checkins, "all_history"
    else:
        chosen, basis = [], "default"

    crowd_vals = [c["crowdedness"] for c in chosen if "crowdedness" in c]
    quiet_vals = [c["quietness"] for c in chosen if "quietness" in c]

    crowd = _avg(crowd_vals, Config.DEFAULT_CROWD)
    quiet = _avg(quiet_vals, Config.DEFAULT_QUIET)

    return {
        "room_id": str(room.get("_id")),
        "name": room.get("name"),
        "crowd": round(crowd, 2),
        "quiet": round(quiet, 2),
        "study_score": _study_score(crowd, quiet),
        "basis": basis,
        "sample_size": len(chosen),
        "target_weekday": target_weekday,
        "target_hour": target_hour,
    }


def rank_rooms_forecast(
    rooms: List[Dict[str, Any]],
    history_by_room: Dict[Any, List[Dict[str, Any]]],
    target_weekday: Optional[int] = None,
    target_hour: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Score and rank rooms for a (weekday, hour). Defaults to "now" in UTC."""
    now = datetime.now(timezone.utc)
    wd = now.weekday() if target_weekday is None else target_weekday
    hr = now.hour if target_hour is None else target_hour

    scored = [
        forecast_score(r, history_by_room.get(r["_id"], []), wd, hr)
        for r in rooms
    ]
    scored.sort(key=lambda x: x["study_score"], reverse=True)
    return scored

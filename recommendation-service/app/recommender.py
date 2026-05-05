from datetime import datetime
from statistics import mean

from .config import Config
from .db import parse_time


def _avg(values, default):
    return float(mean(values)) if values else float(default)


def _study_score(crowd, quiet):
    spaciousness = 6.0 - crowd
    return round(spaciousness + quiet, 2)


def weighted_score(room, live_checkins, historical_checkins, live_weight=None):
    w = Config.LIVE_WEIGHT if live_weight is None else float(live_weight)
    w = max(0.0, min(1.0, w))

    live_crowd = [c["crowdedness"] for c in live_checkins if "crowdedness" in c]
    live_quiet = [c["quietness"] for c in live_checkins if "quietness" in c]
    hist_crowd = [c["crowdedness"] for c in historical_checkins if "crowdedness" in c]
    hist_quiet = [c["quietness"] for c in historical_checkins if "quietness" in c]

    has_live = bool(live_crowd or live_quiet)
    has_hist = bool(hist_crowd or hist_quiet)

    if has_live and has_hist:
        crowd = w * _avg(live_crowd, Config.DEFAULT_CROWD) + (1 - w) * _avg(hist_crowd, Config.DEFAULT_CROWD)
        quiet = w * _avg(live_quiet, Config.DEFAULT_QUIET) + (1 - w) * _avg(hist_quiet, Config.DEFAULT_QUIET)
        source = "live+history"
    elif has_live:
        crowd = _avg(live_crowd, Config.DEFAULT_CROWD)
        quiet = _avg(live_quiet, Config.DEFAULT_QUIET)
        source = "live"
    elif has_hist:
        crowd = _avg(hist_crowd, Config.DEFAULT_CROWD)
        quiet = _avg(hist_quiet, Config.DEFAULT_QUIET)
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
        "live_sample_size": len(live_crowd),
        "history_sample_size": len(hist_crowd),
    }


def rank_rooms_weighted(rooms, live_by_room, history_by_room, live_weight=None):
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


def forecast_score(room, historical_checkins, target_weekday, target_hour):
    exact = []
    same_hour = []

    for c in historical_checkins:
        t = parse_time(c.get("time"))
        if t is None:
            continue
        if t.hour == target_hour:
            same_hour.append(c)
            if t.weekday() == target_weekday:
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


def rank_rooms_forecast(rooms, history_by_room, target_weekday=None, target_hour=None):
    now = datetime.utcnow()
    wd = now.weekday() if target_weekday is None else target_weekday
    hr = now.hour if target_hour is None else target_hour

    scored = [
        forecast_score(r, history_by_room.get(r["_id"], []), wd, hr)
        for r in rooms
    ]
    scored.sort(key=lambda x: x["study_score"], reverse=True)
    return scored

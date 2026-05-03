"""Flask application exposing the recommendation endpoints.

Endpoints
---------
GET  /healthz
    Liveness probe used by Docker / Digital Ocean.

GET  /api/rooms
    List all rooms with their stored "current" snapshot.

GET  /api/recommend
    Live + history blended recommendation (Algorithm 1).
    Query params:
      - live_weight: float in [0, 1], overrides the default blend.
      - top: int, return only the top N rooms.

GET  /api/forecast
    Weekday/hour bucketed forecast (Algorithm 2).
    Query params:
      - weekday: 0=Mon .. 6=Sun (defaults to now, UTC).
      - hour:    0..23 (defaults to now, UTC).
      - top: int, return only the top N rooms.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Flask, jsonify, request
from pymongo.errors import PyMongoError

from . import db as db_module
from .config import Config
from .recommender import rank_rooms_forecast, rank_rooms_weighted


def create_app(db_override=None) -> Flask:
    """Application factory. ``db_override`` lets tests inject a fake DB."""
    app = Flask(__name__)

    def _db():
        return db_override if db_override is not None else db_module.get_db()

    # -----------------------------------------------------------------------
    # Health check
    # -----------------------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "service": "recommendation"}), 200

    # -----------------------------------------------------------------------
    # Rooms listing — useful for the frontend dropdown / debug
    # -----------------------------------------------------------------------
    @app.get("/api/rooms")
    def list_rooms():
        try:
            rooms = db_module.list_rooms(_db())
        except PyMongoError as exc:
            return jsonify({"error": "database_error", "detail": str(exc)}), 503

        return jsonify({"rooms": [_serialize_room(r) for r in rooms]}), 200

    # -----------------------------------------------------------------------
    # Algorithm 1 — live + history blend
    # -----------------------------------------------------------------------
    @app.get("/api/recommend")
    def recommend():
        try:
            live_weight = _parse_float(request.args.get("live_weight"))
            top = _parse_int(request.args.get("top"))
        except ValueError as exc:
            return jsonify({"error": "bad_request", "detail": str(exc)}), 400

        try:
            db = _db()
            rooms = db_module.list_rooms(db)
            live_by_room: Dict[Any, list] = {}
            history_by_room: Dict[Any, list] = {}
            for room in rooms:
                rid = room["_id"]
                live_by_room[rid] = db_module.recent_checkins(db, room_id=rid)
                history_by_room[rid] = db_module.historical_checkins(db, room_id=rid)
        except PyMongoError as exc:
            return jsonify({"error": "database_error", "detail": str(exc)}), 503

        ranked = rank_rooms_weighted(
            rooms, live_by_room, history_by_room, live_weight=live_weight
        )
        if top is not None:
            ranked = ranked[:top]

        return jsonify(
            {
                "algorithm": "weighted",
                "live_weight": live_weight if live_weight is not None else Config.LIVE_WEIGHT,
                "live_window_minutes": Config.LIVE_WINDOW_MINUTES,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "recommendations": ranked,
            }
        ), 200

    # -----------------------------------------------------------------------
    # Algorithm 2 — weekday/hour forecast
    # -----------------------------------------------------------------------
    @app.get("/api/forecast")
    def forecast():
        try:
            weekday = _parse_int(request.args.get("weekday"), lo=0, hi=6)
            hour = _parse_int(request.args.get("hour"), lo=0, hi=23)
            top = _parse_int(request.args.get("top"))
        except ValueError as exc:
            return jsonify({"error": "bad_request", "detail": str(exc)}), 400

        try:
            db = _db()
            rooms = db_module.list_rooms(db)
            history_by_room: Dict[Any, list] = {
                r["_id"]: db_module.historical_checkins(db, room_id=r["_id"])
                for r in rooms
            }
        except PyMongoError as exc:
            return jsonify({"error": "database_error", "detail": str(exc)}), 503

        ranked = rank_rooms_forecast(
            rooms, history_by_room, target_weekday=weekday, target_hour=hour
        )
        if top is not None:
            ranked = ranked[:top]

        now = datetime.now(timezone.utc)
        return jsonify(
            {
                "algorithm": "forecast",
                "target_weekday": weekday if weekday is not None else now.weekday(),
                "target_hour": hour if hour is not None else now.hour,
                "generated_at": now.isoformat(),
                "recommendations": ranked,
            }
        ), 200

    return app


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _serialize_room(room: Dict[str, Any]) -> Dict[str, Any]:
    """Make a room dict JSON-friendly (stringify ObjectId, ISO datetimes)."""
    out: Dict[str, Any] = {}
    for k, v in room.items():
        if k == "_id":
            out["room_id"] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _parse_float(raw):
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"expected a float, got {raw!r}")


def _parse_int(raw, lo=None, hi=None):
    if raw is None or raw == "":
        return None
    try:
        val = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"expected an int, got {raw!r}")
    if lo is not None and val < lo:
        raise ValueError(f"value {val} below minimum {lo}")
    if hi is not None and val > hi:
        raise ValueError(f"value {val} above maximum {hi}")
    return val


# Module-level app for gunicorn. Created lazily so tests don't trigger a
# real Mongo connection just by importing this module.
app = None


def get_app():
    global app
    if app is None:
        app = create_app()
    return app

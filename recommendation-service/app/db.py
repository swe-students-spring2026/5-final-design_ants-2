"""Thin shim. Real DB code lives in the shared top-level `db/` package."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from db.db import client as _shared_client  # noqa: E402, F401
from db.db import db as _shared_db  # noqa: E402
from db.curd import (  # noqa: E402, F401
    get_room,
    historical_checkins,
    list_rooms,
)
from db.curd import recent_checkins as _shared_recent_checkins  # noqa: E402

from .config import Config  # noqa: E402


def get_client(uri=None):
    return _shared_client


def get_db(uri=None, db_name=None):
    return _shared_db


def reset_client():
    """Kept for tests; shared module owns the real lifecycle."""
    pass


def recent_checkins(db=None, room_id=None, minutes=None):
    """Wrap shared recent_checkins so the rec service's LIVE_WINDOW_MINUTES env var still applies."""
    if minutes is None:
        minutes = Config.LIVE_WINDOW_MINUTES
    return _shared_recent_checkins(db, room_id=room_id, minutes=minutes)

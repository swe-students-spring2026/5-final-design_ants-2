"""MongoDB access layer.

This module is intentionally thin — it exposes simple read functions that
return plain dicts/lists so the recommendation logic can stay testable without
needing a live database.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.database import Database

from .config import Config


_client: Optional[MongoClient] = None


def get_client(uri: Optional[str] = None) -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(uri or Config.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db(uri: Optional[str] = None, db_name: Optional[str] = None) -> Database:
    client = get_client(uri)
    return client[db_name or Config.MONGO_DB_NAME]


def reset_client() -> None:
    global _client
    if _client is not None:
        _client.close()
    _client = None


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def list_rooms(db: Database) -> List[Dict[str, Any]]:
    """Return all rooms as a list of dicts."""
    return list(db[Config.COLL_ROOMS].find({}))


def get_room(db: Database, room_id: Any) -> Optional[Dict[str, Any]]:
    """Return a single room by its _id, or None if not found."""
    return db[Config.COLL_ROOMS].find_one({"_id": room_id})


def recent_checkins(
    db: Database,
    room_id: Optional[Any] = None,
    minutes: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return checkins newer than `minutes` ago, optionally filtered by room."""
    window = minutes if minutes is not None else Config.LIVE_WINDOW_MINUTES
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window)
    query: Dict[str, Any] = {"time": {"$gte": cutoff}}
    if room_id is not None:
        query["room_id"] = room_id
    return list(db[Config.COLL_CHECKINS].find(query))


def historical_checkins(
    db: Database,
    room_id: Optional[Any] = None,
    weekday: Optional[int] = None,
    hour: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if room_id is not None:
        query["room_id"] = room_id
    docs = list(db[Config.COLL_CHECKINS].find(query))

    if weekday is None and hour is None:
        return docs

    filtered = []
    for doc in docs:
        t = doc.get("time")
        if not isinstance(t, datetime):
            continue
        if weekday is not None and t.weekday() != weekday:
            continue
        if hour is not None and t.hour != hour:
            continue
        filtered.append(doc)
    return filtered

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from .db import users, rooms, checkins
from .schemas import DEFAULT_USER_EMOJI

LIVE_WINDOW_DEFAULT_MINUTES = 30


def create_user(user_id, username, email, emoji=None):
    existing = users.find_one({"_id": user_id})
    if existing:
        if "emoji" not in existing:
            users.update_one(
                {"_id": user_id},
                {"$set": {"emoji": emoji or DEFAULT_USER_EMOJI}},
            )
            existing["emoji"] = emoji or DEFAULT_USER_EMOJI
        return existing
    now = datetime.now(timezone.utc)

    user = {
        "_id": user_id,
        "username": username,
        "email": email,
        "emoji": emoji or DEFAULT_USER_EMOJI,
        "created_at": now,
        "credits": 0,
    }

    users.insert_one(user)
    return user

def get_user_by_id(user_id):
    return users.find_one({"_id": user_id})


def update_user_emoji(user_id, emoji):
    now = datetime.now(timezone.utc)
    result = users.update_one(
        {"_id": user_id},
        {
            "$set": {"emoji": emoji},
            "$setOnInsert": {
                "username": user_id,
                "email": user_id,
                "created_at": now,
                "credits": 0,
            },
        },
        upsert=True,
    )
    return users.find_one({"_id": result.upserted_id or user_id})

def get_all_rooms():
    return list(rooms.find())


def get_room_by_id(room_id):
    return rooms.find_one({"_id": room_id})


def list_rooms(db: Optional[Database] = None) -> List[Dict[str, Any]]:
    coll = db[rooms.name] if db is not None else rooms
    return list(coll.find({}))


def get_room(db: Optional[Database], room_id: Any) -> Optional[Dict[str, Any]]:
    coll = db[rooms.name] if db is not None else rooms
    return coll.find_one({"_id": room_id})


def recent_checkins(
    db: Optional[Database] = None,
    room_id: Optional[Any] = None,
    minutes: Optional[int] = None,
) -> List[Dict[str, Any]]:
    coll = db[checkins.name] if db is not None else checkins
    window = minutes if minutes is not None else LIVE_WINDOW_DEFAULT_MINUTES
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window)
    query: Dict[str, Any] = {"time": {"$gte": cutoff}}
    if room_id is not None:
        query["room_id"] = room_id
    return list(coll.find(query))


def historical_checkins(
    db: Optional[Database] = None,
    room_id: Optional[Any] = None,
    weekday: Optional[int] = None,
    hour: Optional[int] = None,
) -> List[Dict[str, Any]]:
    coll = db[checkins.name] if db is not None else checkins
    query: Dict[str, Any] = {}
    if room_id is not None:
        query["room_id"] = room_id
    docs = list(coll.find(query))
    if weekday is None and hour is None:
        return docs
    out = []
    for d in docs:
        t = d.get("time")
        if not isinstance(t, datetime):
            continue
        if weekday is not None and t.weekday() != weekday:
            continue
        if hour is not None and t.hour != hour:
            continue
        out.append(d)
    return out


def create_checkin(user_id, room_id, crowdedness, quietness):
    user = users.find_one({"_id": user_id})
    if not user:
        raise ValueError(f"User does not exist: {user_id}")
    
    now = datetime.now(timezone.utc)

    room = rooms.find_one({"_id": room_id})
    if not room:
        raise ValueError(f"Room does not exist: {room_id}")

    if crowdedness < 1 or crowdedness > 5:
        raise ValueError("crowdedness must be between 1 and 5")

    if quietness < 1 or quietness > 5:
        raise ValueError("quietness must be between 1 and 5")

    checkin = {
        "user_id": user_id,
        "room_id": room_id,
        "time": now,
        "crowdedness": crowdedness,
        "quietness": quietness,
    }

    result = checkins.insert_one(checkin)

    rooms.update_one(
        {"_id": room_id},
        {
            "$set": {
                "current_crowd": crowdedness,
                "current_quiet": quietness,
                "last_updated": now,
            }
        },
    )

    users.update_one(
        {"_id": user_id},
        {"$inc": {"credits": 1}},
    )

    checkin["_id"] = result.inserted_id
    return checkin


def get_checkins_by_user(user_id):
    return list(checkins.find({"user_id": user_id}).sort("time", -1))


def get_checkins_by_room(room_id):
    return list(checkins.find({"room_id": room_id}).sort("time", -1))

def update_room_status(room_id, crowdedness, quietness, updated_at=None):

    if not isinstance(crowdedness, int) or not 1 <= crowdedness <= 5:
        raise ValueError("crowdedness must be an integer between 1 and 5")

    if not isinstance(quietness, int) or not 1 <= quietness <= 5:
        raise ValueError("quietness must be an integer between 1 and 5")

    if updated_at is None:
        updated_at = datetime.now(timezone.utc)

    result = rooms.update_one(
        {"_id": room_id},
        {
            "$set": {
                "current_crowd": crowdedness,
                "current_quiet": quietness,
                "last_updated": updated_at,
            }
        },
    )

    if result.matched_count == 0:
        raise ValueError(f"Room does not exist: {room_id}")

    return rooms.find_one({"_id": room_id})

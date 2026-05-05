from datetime import datetime, timedelta

from pymongo import MongoClient

from .config import Config


client = MongoClient(Config.MONGO_URI)
db = client[Config.DB_NAME]

rooms_collection = db["rooms"]
checkins_collection = db["checkins"]


def list_rooms():
    return list(rooms_collection.find({}))


def get_room(room_id):
    return rooms_collection.find_one({"_id": room_id})


def recent_checkins(room_id=None, minutes=None):
    window = minutes if minutes is not None else Config.LIVE_WINDOW_MINUTES
    cutoff = (datetime.utcnow() - timedelta(minutes=window)).isoformat()
    query = {"time": {"$gte": cutoff}}
    if room_id is not None:
        query["room_id"] = room_id
    return list(checkins_collection.find(query))


def historical_checkins(room_id=None, weekday=None, hour=None):
    query = {}
    if room_id is not None:
        query["room_id"] = room_id
    docs = list(checkins_collection.find(query))

    if weekday is None and hour is None:
        return docs

    filtered = []
    for doc in docs:
        t = parse_time(doc.get("time"))
        if t is None:
            continue
        if weekday is not None and t.weekday() != weekday:
            continue
        if hour is not None and t.hour != hour:
            continue
        filtered.append(doc)
    return filtered


def parse_time(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None

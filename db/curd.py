from datetime import datetime, timezone
from .db import users, rooms, checkins


def create_user(user_id, username, email):
    now = datetime.now(timezone.utc)

    user = {
        "_id": user_id,
        "username": username,
        "email": email,
        "created_at": now,
        "credits": 0,
    }

    users.insert_one(user)
    return user

def get_user_by_id(user_id):
    return users.find_one({"_id": user_id})

def get_all_rooms():
    return list(rooms.find())


def get_room_by_id(room_id):
    return rooms.find_one({"_id": room_id})


def create_checkin(user_id, room_id, crowdedness, quietness):
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
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime, timezone
from db.db import checkins as checkins_collection, rooms as rooms_collection, users as users_collection
from db.schemas import DEFAULT_USER_EMOJI

bp = Blueprint("main", __name__)
EMOJI_MAX_LENGTH = 16
CHECKIN_COOLDOWN_SECONDS = 30 * 60


def _serialize_user(user):
    if not user:
        return None
    created_at = user.get("created_at")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return {
        "_id": str(user["_id"]),
        "username": user.get("username") or str(user["_id"]),
        "email": user.get("email") or "",
        "emoji": user.get("emoji") or DEFAULT_USER_EMOJI,
        "created_at": created_at,
        "credits": user.get("credits", 0),
    }


def _clean_emoji(value):
    if not isinstance(value, str):
        return None
    emoji = value.strip()
    if not emoji or len(emoji) > EMOJI_MAX_LENGTH:
        return None
    return emoji


def _checkin_datetime(value):
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, str):
        try:
            checkin_time = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if checkin_time.tzinfo:
            checkin_time = checkin_time.astimezone(timezone.utc).replace(tzinfo=None)
        return checkin_time
    return None


def _checkin_cooldown_remaining(user_id):
    latest = checkins_collection.find_one({"user_id": user_id}, sort=[("time", -1)])
    if not latest:
        return 0

    latest_time = _checkin_datetime(latest.get("time"))
    if not latest_time:
        return 0

    elapsed = datetime.utcnow() - latest_time
    return max(0, CHECKIN_COOLDOWN_SECONDS - int(elapsed.total_seconds()))


@bp.route("/")
def home():
    return render_template("index.html")


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@bp.route("/api/rooms", methods=["GET"])
def get_rooms():
    rooms = list(
        rooms_collection.find(
            {},
            {
                "_id": 1,
                "name": 1,
                "current_crowd": 1,
                "current_quiet": 1,
                "last_updated": 1
            }
        )
    )

    for room in rooms:
        room["_id"] = str(room["_id"])

    return jsonify(rooms), 200


@bp.route("/api/users", methods=["POST"])
def upsert_user():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = str(data.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"error": "Missing field: user_id"}), 400

    existing = users_collection.find_one({"_id": user_id})
    now = datetime.utcnow()
    username = str(data.get("username") or user_id).strip()
    email = str(data.get("email") or "").strip()
    update = {
        "$set": {
            "username": username or user_id,
            "email": email,
        },
        "$setOnInsert": {
            "created_at": now,
            "credits": 0,
            "emoji": DEFAULT_USER_EMOJI,
        },
    }

    if "emoji" in data:
        emoji = _clean_emoji(data.get("emoji"))
        if not emoji:
            return jsonify({"error": "Invalid emoji"}), 400
        update["$set"]["emoji"] = emoji
        update["$setOnInsert"].pop("emoji", None)

    users_collection.update_one({"_id": user_id}, update, upsert=True)
    user = users_collection.find_one({"_id": user_id})
    return jsonify({"user": _serialize_user(user)}), 200 if existing else 201


@bp.route("/api/users/<path:user_id>", methods=["GET"])
def get_user(user_id):
    user = users_collection.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404
    if "emoji" not in user:
        users_collection.update_one(
            {"_id": user_id},
            {"$set": {"emoji": DEFAULT_USER_EMOJI}},
        )
        user["emoji"] = DEFAULT_USER_EMOJI
    return jsonify({"user": _serialize_user(user)}), 200


@bp.route("/api/users/<path:user_id>/emoji", methods=["PUT"])
def update_user_emoji(user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    emoji = _clean_emoji(data.get("emoji"))
    if not emoji:
        return jsonify({"error": "Invalid emoji"}), 400

    now = datetime.utcnow()
    users_collection.update_one(
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
    user = users_collection.find_one({"_id": user_id})
    return jsonify({"user": _serialize_user(user)}), 200


@bp.route("/api/checkins", methods=["POST"])
def create_checkin():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    required_fields = ["user_id", "room_id", "crowdedness", "quietness"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    user_id = str(data["user_id"]).strip()
    if not user_id:
        return jsonify({"error": "Missing field: user_id"}), 400

    remaining = _checkin_cooldown_remaining(user_id)
    if remaining > 0 and data.get("debug_bypass_cooldown") is not True:
        return jsonify(
            {
                "error": "Punch cooldown active",
                "retry_after_seconds": remaining,
            }
        ), 429

    crowdedness = data["crowdedness"]
    quietness = data["quietness"]
    room_id = data["room_id"]

    if not isinstance(crowdedness, int) or crowdedness < 1 or crowdedness > 5:
        return jsonify({"error": "crowdedness must be an integer between 1 and 5"}), 400

    if not isinstance(quietness, int) or quietness < 1 or quietness > 5:
        return jsonify({"error": "quietness must be an integer between 1 and 5"}), 400

    room = rooms_collection.find_one({"_id": room_id})
    if not room:
        return jsonify({"error": "Invalid room_id"}), 400

    current_time = datetime.utcnow().isoformat()

    checkin_doc = {
        "user_id": user_id,
        "room_id": room_id,
        "time": current_time,
        "crowdedness": crowdedness,
        "quietness": quietness,
    }

    result = checkins_collection.insert_one(checkin_doc)

    rooms_collection.update_one(
        {"_id": room_id},
        {
            "$set": {
                "current_crowd": crowdedness,
                "current_quiet": quietness,
                "last_updated": current_time
            }
        }
    )

    checkin_doc["_id"] = str(result.inserted_id)

    return jsonify({
        "message": "Check-in created successfully",
        "checkin": checkin_doc
    }), 201


@bp.route("/api/checkins/<user_id>", methods=["GET"])
def get_user_checkins(user_id):
    records = list(
        checkins_collection.find({"user_id": user_id}, {"_id": 0}).sort("time", -1)
    )
    return jsonify(records), 200

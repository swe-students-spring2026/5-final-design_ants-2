from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
from db import checkins_collection, rooms_collection

bp = Blueprint("main", __name__)


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


@bp.route("/api/checkins", methods=["POST"])
def create_checkin():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    required_fields = ["user_id", "room_id", "crowdedness", "quietness"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

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
        "user_id": data["user_id"],
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
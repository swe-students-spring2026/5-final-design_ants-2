from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

CHECKIN_API = os.getenv("CHECKIN_API", "http://checkin-service:5000")
RECOMMENDATION_API = os.getenv("RECOMMENDATION_API", "http://recommendation-service:8000")

@app.route("/")
def index():
    try:
        rooms_resp = requests.get(f"{CHECKIN_API}/api/rooms", timeout=5)
        rooms = rooms_resp.json() if rooms_resp.status_code == 200 else []
    except Exception as e:
        rooms = [{"error": str(e)}]

    try:
        rec_resp = requests.get(f"{RECOMMENDATION_API}/api/recommend?top=5", timeout=5)
        recommendations = rec_resp.json().get("recommendations", []) if rec_resp.status_code == 200 else []
    except Exception as e:
        recommendations = [{"error": str(e)}]

    return render_template("index.html", rooms=rooms, recommendations=recommendations)

@app.route("/checkin", methods=["POST"])
def checkin():
    user_id = request.form.get("user_id", "dummy_user")
    room_id = request.form.get("room_id")
    crowdedness = int(request.form.get("crowdedness", 3))
    quietness = int(request.form.get("quietness", 3))

    payload = {
        "user_id": user_id,
        "room_id": room_id,
        "crowdedness": crowdedness,
        "quietness": quietness
    }

    try:
        resp = requests.post(f"{CHECKIN_API}/api/checkins", json=payload, timeout=5)
        if resp.status_code == 201:
            return "Checkin successful! <a href='/'>Go back</a>"
        else:
            return f"Checkin failed: {resp.text} <br><a href='/'>Go back</a>"
    except Exception as e:
        return f"Error: {str(e)} <br><a href='/'>Go back</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
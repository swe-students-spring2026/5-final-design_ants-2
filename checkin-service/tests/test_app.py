import pytest
from app import create_app
from db import checkins_collection, rooms_collection


@pytest.fixture
def client():
    checkins_collection.delete_many({})
    rooms_collection.delete_many({})

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

    checkins_collection.delete_many({})
    rooms_collection.delete_many({})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_get_rooms(client):
    response = client.get("/api/rooms")
    assert response.status_code == 200
    assert isinstance(response.json, list)
    assert len(response.json) > 0
    assert "_id" in response.json[0]
    assert "name" in response.json[0]


def test_create_checkin_success(client):
    payload = {
        "user_id": "zelu",
        "room_id": "bobst_3",
        "crowdedness": 4,
        "quietness": 2
    }

    response = client.post("/api/checkins", json=payload)
    assert response.status_code == 201

    data = response.get_json()
    assert data["message"] == "Check-in created successfully"
    assert data["checkin"]["user_id"] == "zelu"
    assert data["checkin"]["room_id"] == "bobst_3"
    assert data["checkin"]["crowdedness"] == 4
    assert data["checkin"]["quietness"] == 2
    assert "time" in data["checkin"]


def test_create_checkin_missing_field(client):
    payload = {
        "user_id": "zelu",
        "room_id": "bobst_3",
        "crowdedness": 4
    }

    response = client.post("/api/checkins", json=payload)
    assert response.status_code == 400
    assert "Missing field" in response.get_json()["error"]


def test_create_checkin_invalid_room(client):
    payload = {
        "user_id": "zelu",
        "room_id": "invalid_room",
        "crowdedness": 4,
        "quietness": 2
    }

    response = client.post("/api/checkins", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid room_id"


def test_create_checkin_invalid_crowdedness(client):
    payload = {
        "user_id": "zelu",
        "room_id": "bobst_3",
        "crowdedness": 10,
        "quietness": 2
    }

    response = client.post("/api/checkins", json=payload)
    assert response.status_code == 400
    assert "crowdedness must be an integer between 1 and 5" in response.get_json()["error"]


def test_create_checkin_invalid_quietness(client):
    payload = {
        "user_id": "zelu",
        "room_id": "bobst_3",
        "crowdedness": 4,
        "quietness": 10
    }

    response = client.post("/api/checkins", json=payload)
    assert response.status_code == 400
    assert "quietness must be an integer between 1 and 5" in response.get_json()["error"]


def test_get_user_checkins(client):
    payload1 = {
        "user_id": "zelu",
        "room_id": "bobst_2",
        "crowdedness": 3,
        "quietness": 4
    }

    payload2 = {
        "user_id": "zelu",
        "room_id": "bobst_4",
        "crowdedness": 2,
        "quietness": 5
    }

    client.post("/api/checkins", json=payload1)
    client.post("/api/checkins", json=payload2)

    response = client.get("/api/checkins/zelu")
    assert response.status_code == 200

    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["user_id"] == "zelu"


def test_room_status_updated_after_checkin(client):
    payload = {
        "user_id": "zelu",
        "room_id": "bobst_ll1",
        "crowdedness": 5,
        "quietness": 1
    }

    response = client.post("/api/checkins", json=payload)
    assert response.status_code == 201

    room = rooms_collection.find_one({"_id": "bobst_ll1"})
    assert room["current_crowd"] == 5
    assert room["current_quiet"] == 1
    assert room["last_updated"] is not None
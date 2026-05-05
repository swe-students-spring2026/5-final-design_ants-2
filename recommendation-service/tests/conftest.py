from datetime import datetime, timedelta

import pytest

from app.db import checkins_collection, rooms_collection
from app.main import create_app


@pytest.fixture
def client():
    rooms_collection.delete_many({})
    checkins_collection.delete_many({})

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as c:
        yield c

    rooms_collection.delete_many({})
    checkins_collection.delete_many({})


@pytest.fixture
def seeded(client):
    rooms_collection.insert_many([
        {"_id": "r1", "name": "Room 1", "current_crowd": None,
         "current_quiet": None, "last_updated": None},
        {"_id": "r2", "name": "Room 2", "current_crowd": None,
         "current_quiet": None, "last_updated": None},
    ])

    now = datetime.utcnow()
    live = (now - timedelta(minutes=5)).isoformat()
    old = (now - timedelta(days=3)).isoformat()

    checkins_collection.insert_many([
        {"user_id": "u1", "room_id": "r1", "time": live, "crowdedness": 2, "quietness": 5},
        {"user_id": "u2", "room_id": "r1", "time": live, "crowdedness": 1, "quietness": 4},
        {"user_id": "u3", "room_id": "r2", "time": live, "crowdedness": 5, "quietness": 1},
        {"user_id": "u1", "room_id": "r1", "time": old, "crowdedness": 3, "quietness": 3},
        {"user_id": "u2", "room_id": "r1", "time": old, "crowdedness": 4, "quietness": 2},
        {"user_id": "u3", "room_id": "r2", "time": old, "crowdedness": 2, "quietness": 4},
    ])
    return client

from datetime import datetime, timedelta, timezone

import pytest

from db.curd import (
    create_checkin,
    create_user,
    get_all_rooms,
    get_checkins_by_room,
    get_checkins_by_user,
    get_room_by_id,
    get_user_by_id,
    update_room_status,
)
from db.schemas import DEFAULT_USER_EMOJI, ROOMS_SEED
from db.seed_data import seed_rooms


REQUIRED_ROOM_FIELDS = {
    "_id",
    "name",
    "floor",
    "capacity",
    "current_crowd",
    "current_quiet",
    "last_updated",
}


def test_seed_rooms_inserts_all_rooms_when_empty(isolated_db):
    seed_rooms()

    seeded_rooms = isolated_db["rooms"].find({})
    assert len(seeded_rooms) == len(ROOMS_SEED)
    assert {room["_id"] for room in seeded_rooms} == {
        room["_id"] for room in ROOMS_SEED
    }


def test_seed_rooms_does_not_duplicate_rooms(isolated_db):
    seed_rooms()
    seed_rooms()

    assert isolated_db["rooms"].count_documents({}) == len(ROOMS_SEED)


def test_seeded_rooms_contain_required_fields(isolated_db):
    seed_rooms()

    for room in isolated_db["rooms"].find({}):
        assert REQUIRED_ROOM_FIELDS.issubset(room.keys())


def test_create_user_inserts_user_with_default_values(isolated_db):
    user = create_user("u1", "Ada", "ada@example.com")

    assert user["_id"] == "u1"
    assert user["username"] == "Ada"
    assert user["email"] == "ada@example.com"
    assert user["emoji"] == DEFAULT_USER_EMOJI
    assert user["created_at"] is not None
    assert user["credits"] == 0
    assert isolated_db["users"].count_documents({}) == 1


def test_create_user_uses_provided_emoji(isolated_db):
    user = create_user("u1", "Ada", "ada@example.com", emoji=":)")

    assert user["emoji"] == ":)"


def test_create_user_returns_existing_user_without_duplicate(isolated_db):
    original = create_user("u1", "Ada", "ada@example.com")
    existing = create_user("u1", "Changed", "changed@example.com", emoji=":)")

    assert existing == original
    assert isolated_db["users"].count_documents({"_id": "u1"}) == 1


def test_get_user_by_id_returns_inserted_user():
    user = create_user("u1", "Ada", "ada@example.com")

    assert get_user_by_id("u1") == user


def test_get_user_by_id_returns_none_for_missing_user():
    assert get_user_by_id("missing") is None


def test_get_all_rooms_returns_seeded_rooms():
    seed_rooms()

    rooms = get_all_rooms()
    assert len(rooms) == len(ROOMS_SEED)


def test_get_room_by_id_returns_matching_room():
    seed_rooms()

    room = get_room_by_id(ROOMS_SEED[0]["_id"])
    assert room["_id"] == ROOMS_SEED[0]["_id"]
    assert room["name"] == ROOMS_SEED[0]["name"]


def test_get_room_by_id_returns_none_for_missing_room():
    seed_rooms()

    assert get_room_by_id("missing") is None


def test_create_checkin_inserts_checkin_and_updates_room_and_user():
    seed_rooms()
    create_user("u1", "Ada", "ada@example.com")
    room_id = ROOMS_SEED[0]["_id"]

    checkin = create_checkin("u1", room_id, crowdedness=4, quietness=2)

    assert checkin["_id"] is not None
    assert checkin["user_id"] == "u1"
    assert checkin["room_id"] == room_id
    assert checkin["time"] is not None
    assert checkin["crowdedness"] == 4
    assert checkin["quietness"] == 2

    room = get_room_by_id(room_id)
    assert room["current_crowd"] == 4
    assert room["current_quiet"] == 2
    assert room["last_updated"] is not None

    user = get_user_by_id("u1")
    assert user["credits"] == 1


def test_create_checkin_raises_if_user_does_not_exist():
    seed_rooms()

    with pytest.raises(ValueError):
        create_checkin("missing", ROOMS_SEED[0]["_id"], crowdedness=3, quietness=3)


def test_create_checkin_raises_if_room_does_not_exist():
    create_user("u1", "Ada", "ada@example.com")

    with pytest.raises(ValueError):
        create_checkin("u1", "missing", crowdedness=3, quietness=3)


@pytest.mark.parametrize("crowdedness", [0, 6])
def test_create_checkin_raises_for_invalid_crowdedness(crowdedness):
    seed_rooms()
    create_user("u1", "Ada", "ada@example.com")

    with pytest.raises(ValueError):
        create_checkin("u1", ROOMS_SEED[0]["_id"], crowdedness=crowdedness, quietness=3)


@pytest.mark.parametrize("quietness", [0, 6])
def test_create_checkin_raises_for_invalid_quietness(quietness):
    seed_rooms()
    create_user("u1", "Ada", "ada@example.com")

    with pytest.raises(ValueError):
        create_checkin("u1", ROOMS_SEED[0]["_id"], crowdedness=3, quietness=quietness)


def test_get_checkins_by_user_returns_only_user_checkins_sorted_desc(isolated_db):
    now = datetime.now(timezone.utc)
    isolated_db["checkins"].insert_many(
        [
            {
                "user_id": "u1",
                "room_id": "r1",
                "time": now - timedelta(minutes=10),
                "crowdedness": 2,
                "quietness": 3,
            },
            {
                "user_id": "u2",
                "room_id": "r1",
                "time": now,
                "crowdedness": 5,
                "quietness": 1,
            },
            {
                "user_id": "u1",
                "room_id": "r2",
                "time": now - timedelta(minutes=1),
                "crowdedness": 4,
                "quietness": 4,
            },
        ]
    )

    results = get_checkins_by_user("u1")

    assert [checkin["user_id"] for checkin in results] == ["u1", "u1"]
    assert [checkin["time"] for checkin in results] == sorted(
        [checkin["time"] for checkin in results], reverse=True
    )


def test_get_checkins_by_room_returns_only_room_checkins_sorted_desc(isolated_db):
    now = datetime.now(timezone.utc)
    isolated_db["checkins"].insert_many(
        [
            {
                "user_id": "u1",
                "room_id": "r1",
                "time": now - timedelta(minutes=10),
                "crowdedness": 2,
                "quietness": 3,
            },
            {
                "user_id": "u2",
                "room_id": "r2",
                "time": now,
                "crowdedness": 5,
                "quietness": 1,
            },
            {
                "user_id": "u3",
                "room_id": "r1",
                "time": now - timedelta(minutes=1),
                "crowdedness": 4,
                "quietness": 4,
            },
        ]
    )

    results = get_checkins_by_room("r1")

    assert [checkin["room_id"] for checkin in results] == ["r1", "r1"]
    assert [checkin["time"] for checkin in results] == sorted(
        [checkin["time"] for checkin in results], reverse=True
    )


def test_update_room_status_updates_values_and_uses_provided_updated_at():
    seed_rooms()
    room_id = ROOMS_SEED[0]["_id"]
    updated_at = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)

    room = update_room_status(room_id, crowdedness=5, quietness=1, updated_at=updated_at)

    assert room["current_crowd"] == 5
    assert room["current_quiet"] == 1
    assert room["last_updated"] == updated_at


@pytest.mark.parametrize("crowdedness", [0, 6, 3.5, "3"])
def test_update_room_status_raises_for_invalid_crowdedness(crowdedness):
    seed_rooms()

    with pytest.raises(ValueError):
        update_room_status(ROOMS_SEED[0]["_id"], crowdedness=crowdedness, quietness=3)


@pytest.mark.parametrize("quietness", [0, 6, 3.5, "3"])
def test_update_room_status_raises_for_invalid_quietness(quietness):
    seed_rooms()

    with pytest.raises(ValueError):
        update_room_status(ROOMS_SEED[0]["_id"], crowdedness=3, quietness=quietness)


def test_update_room_status_raises_if_room_does_not_exist():
    with pytest.raises(ValueError):
        update_room_status("missing", crowdedness=3, quietness=3)

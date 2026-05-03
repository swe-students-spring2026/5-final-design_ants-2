USERS_COLLECTION = "users"
ROOMS_COLLECTION = "rooms"
CHECKINS_COLLECTION = "checkins"

ROOM_IDS = [
    "bobst_ll1",
    "bobst_2",
    "bobst_3",
    "bobst_4",
]

CROWD_MIN = 1
CROWD_MAX = 5
QUIET_MIN = 1
QUIET_MAX = 5

ROOMS_SEED = [
    {
        "_id": "bobst_ll1",
        "name": "Bobst LL1",
        "floor": "LL1",
        "capacity": 250,
        "current_crowd": None,
        "current_quiet": None,
        "last_updated": None,
    },
    {
        "_id": "bobst_2",
        "name": "Bobst 2F",
        "floor": "2",
        "capacity": 180,
        "current_crowd": None,
        "current_quiet": None,
        "last_updated": None,
    },
]

import os


class Config:

    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "library_app")

    COLL_USERS = os.environ.get("COLL_USERS", "users")
    COLL_CHECKINS = os.environ.get("COLL_CHECKINS", "checkins")
    COLL_ROOMS = os.environ.get("COLL_ROOMS", "rooms")

    LIVE_WINDOW_MINUTES = int(os.environ.get("LIVE_WINDOW_MINUTES", "30"))

    LIVE_WEIGHT = float(os.environ.get("LIVE_WEIGHT", "0.7"))

    DEFAULT_CROWD = float(os.environ.get("DEFAULT_CROWD", "3.0"))
    DEFAULT_QUIET = float(os.environ.get("DEFAULT_QUIET", "3.0"))

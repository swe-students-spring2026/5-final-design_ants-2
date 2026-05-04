import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    DB_NAME = os.getenv("DB_NAME", "nyu_library_app")

    LIVE_WINDOW_MINUTES = int(os.getenv("LIVE_WINDOW_MINUTES", "30"))
    LIVE_WEIGHT = float(os.getenv("LIVE_WEIGHT", "0.7"))
    DEFAULT_CROWD = float(os.getenv("DEFAULT_CROWD", "3.0"))
    DEFAULT_QUIET = float(os.getenv("DEFAULT_QUIET", "3.0"))

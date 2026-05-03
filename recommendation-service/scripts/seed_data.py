import os
import random
import sys
from datetime import datetime, timedelta, timezone

# Make `app` importable regardless of how this script is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo.errors import ServerSelectionTimeoutError  # noqa: E402

from app.config import Config  # noqa: E402
from app.db import get_db  # noqa: E402


ROOMS = [
    {"_id": "bbst-3f", "name": "BBST 3F"},
    {"_id": "bbst-5f", "name": "BBST 5F"},
    {"_id": "bbst-lc", "name": "BBST Learning Commons"},
]


def seed(num_history: int = 200) -> None:
    print(f"Connecting to {Config.MONGO_URI} (db={Config.MONGO_DB_NAME})...")
    db = get_db()

    try:
        db.client.admin.command("ping")
    except ServerSelectionTimeoutError as exc:
        print(f"\nERROR: could not reach MongoDB at {Config.MONGO_URI}.")
        print("Is the database running? Try `docker compose up -d mongo` first.")
        print(f"\nUnderlying error: {exc}")
        sys.exit(1)

    db[Config.COLL_ROOMS].drop()
    db[Config.COLL_CHECKINS].drop()

    db[Config.COLL_ROOMS].insert_many(
        [
            {**r, "current_crowd": 3, "current_quiet": 3,
             "last_updated": datetime.now(timezone.utc)}
            for r in ROOMS
        ]
    )

    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    docs = []
    for i in range(num_history):
        room = rng.choice(ROOMS)
        offset = timedelta(
            days=rng.randint(0, 29),
            hours=rng.randint(7, 22),
            minutes=rng.randint(0, 59),
        )
        t = now - offset
        if 15 <= t.hour <= 19:
            crowd = rng.randint(3, 5)
            quiet = rng.randint(1, 3)
        else:
            crowd = rng.randint(1, 3)
            quiet = rng.randint(3, 5)
        docs.append(
            {
                "_id": f"seed-{i}",
                "user_id": f"user-{rng.randint(1, 25)}",
                "room_id": room["_id"],
                "time": t,
                "crowdedness": crowd,
                "quietness": quiet,
            }
        )
    db[Config.COLL_CHECKINS].insert_many(docs)
    print(f"Seeded {len(ROOMS)} rooms and {len(docs)} checkins into "
          f"`{Config.MONGO_DB_NAME}`.")


if __name__ == "__main__":
    seed()

import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import checkins_collection, rooms_collection  # noqa: E402


ROOMS = [
    {"_id": "bobst_ll1", "name": "Bobst LL1"},
    {"_id": "bobst_2", "name": "Bobst 2nd Floor"},
    {"_id": "bobst_3", "name": "Bobst 3rd Floor"},
    {"_id": "bobst_4", "name": "Bobst 4th Floor"},
]


def seed(num_history=200):
    rooms_collection.drop()
    checkins_collection.drop()

    rooms_collection.insert_many([
        {**r, "current_crowd": None, "current_quiet": None, "last_updated": None}
        for r in ROOMS
    ])

    rng = random.Random(42)
    now = datetime.utcnow()
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
        docs.append({
            "user_id": f"user-{rng.randint(1, 25)}",
            "room_id": room["_id"],
            "time": t.isoformat(),
            "crowdedness": crowd,
            "quietness": quiet,
        })
    checkins_collection.insert_many(docs)
    print(f"Seeded {len(ROOMS)} rooms and {len(docs)} checkins.")


if __name__ == "__main__":
    seed()

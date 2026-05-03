"""Seed shared MongoDB with starter rooms.

Run once after first bringing up the stack:
    python -m db.seed_data
"""
from .db import rooms
from .schemas import ROOMS_SEED


def seed_rooms():
    if rooms.count_documents({}) == 0:
        rooms.insert_many(ROOMS_SEED)
        print(f"Seeded {len(ROOMS_SEED)} rooms.")
    else:
        print("Rooms collection already populated; skipping.")


if __name__ == "__main__":
    seed_rooms()

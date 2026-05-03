from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest


class FakeCollection:
    def __init__(self, docs=None):
        self.docs: List[Dict[str, Any]] = list(docs or [])

    def _matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, cond in query.items():
            if isinstance(cond, dict) and "$gte" in cond:
                value = doc.get(key)
                if value is None or value < cond["$gte"]:
                    return False
            else:
                if doc.get(key) != cond:
                    return False
        return True

    def find(self, query=None):
        query = query or {}
        return [d for d in self.docs if self._matches(d, query)]

    def find_one(self, query=None):
        results = self.find(query)
        return results[0] if results else None

    def insert_many(self, docs):
        self.docs.extend(docs)


class FakeDB:
    def __init__(self):
        self.collections: Dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def now_utc():
    return datetime.now(timezone.utc)


@pytest.fixture
def seeded_db(fake_db, now_utc):
    """A database with two rooms and a mix of live and historical checkins."""
    fake_db["rooms"].insert_many(
        [
            {"_id": "r1", "name": "BBST 5F", "current_crowd": 2, "current_quiet": 4},
            {"_id": "r2", "name": "BBST 3F", "current_crowd": 5, "current_quiet": 2},
        ]
    )

    live = now_utc - timedelta(minutes=5)
    old = now_utc - timedelta(days=3)

    fake_db["checkins"].insert_many(
        [
            # Live checkins for r1: empty and quiet
            {"_id": "c1", "user_id": "u1", "room_id": "r1", "time": live,
             "crowdedness": 2, "quietness": 5},
            {"_id": "c2", "user_id": "u2", "room_id": "r1", "time": live,
             "crowdedness": 1, "quietness": 4},
            # Live checkins for r2: packed and loud
            {"_id": "c3", "user_id": "u3", "room_id": "r2", "time": live,
             "crowdedness": 5, "quietness": 1},
            # Historical checkins (3 days ago — outside the live window)
            {"_id": "c4", "user_id": "u1", "room_id": "r1", "time": old,
             "crowdedness": 3, "quietness": 3},
            {"_id": "c5", "user_id": "u2", "room_id": "r1", "time": old,
             "crowdedness": 4, "quietness": 2},
            {"_id": "c6", "user_id": "u3", "room_id": "r2", "time": old,
             "crowdedness": 2, "quietness": 4},
        ]
    )
    return fake_db

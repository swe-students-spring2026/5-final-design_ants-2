from copy import deepcopy

import pytest


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(self, matched_count, upserted_id=None):
        self.matched_count = matched_count
        self.upserted_id = upserted_id


class FakeCursor(list):
    def sort(self, field, direction):
        reverse = direction == -1
        return FakeCursor(
            sorted(self, key=lambda doc: doc.get(field), reverse=reverse)
        )


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self._docs = []
        self._next_id = 1

    def delete_many(self, query):
        if query == {}:
            self._docs.clear()
            return
        self._docs = [doc for doc in self._docs if not self._matches(doc, query)]

    def count_documents(self, query):
        return len([doc for doc in self._docs if self._matches(doc, query)])

    def insert_one(self, doc):
        stored = deepcopy(doc)
        if "_id" not in stored:
            stored["_id"] = f"{self.name}_{self._next_id}"
            self._next_id += 1
            doc["_id"] = stored["_id"]
        self._docs.append(stored)
        return InsertOneResult(stored["_id"])

    def insert_many(self, docs):
        for doc in docs:
            self.insert_one(doc)

    def find_one(self, query):
        for doc in self._docs:
            if self._matches(doc, query):
                return deepcopy(doc)
        return None

    def find(self, query=None):
        query = query or {}
        return FakeCursor(
            [deepcopy(doc) for doc in self._docs if self._matches(doc, query)]
        )

    def update_one(self, query, update, upsert=False):
        for doc in self._docs:
            if self._matches(doc, query):
                self._apply_update(doc, update, is_insert=False)
                return UpdateResult(matched_count=1)

        if not upsert:
            return UpdateResult(matched_count=0)

        new_doc = deepcopy(query)
        self._apply_update(new_doc, update, is_insert=True)
        self.insert_one(new_doc)
        return UpdateResult(matched_count=0, upserted_id=new_doc.get("_id"))

    def _apply_update(self, doc, update, is_insert):
        for field, value in update.get("$set", {}).items():
            doc[field] = value
        for field, value in update.get("$inc", {}).items():
            doc[field] = doc.get(field, 0) + value
        if is_insert:
            for field, value in update.get("$setOnInsert", {}).items():
                doc[field] = value

    def _matches(self, doc, query):
        for field, expected in query.items():
            actual = doc.get(field)
            if isinstance(expected, dict):
                if "$gte" in expected and actual < expected["$gte"]:
                    return False
            elif actual != expected:
                return False
        return True


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    from db import curd, seed_data

    users = FakeCollection("users")
    rooms = FakeCollection("rooms")
    checkins = FakeCollection("checkins")

    monkeypatch.setattr(curd, "users", users)
    monkeypatch.setattr(curd, "rooms", rooms)
    monkeypatch.setattr(curd, "checkins", checkins)
    monkeypatch.setattr(seed_data, "rooms", rooms)

    yield {
        "users": users,
        "rooms": rooms,
        "checkins": checkins,
    }

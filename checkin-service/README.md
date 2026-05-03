# Checkin Service

Backend microservice that handles **room check-ins** for the library crowdedness app. Users submit crowdedness and quietness ratings for a room; the service stores the report in MongoDB and updates that room's live snapshot so the rest of the system always has fresh data.

This subsystem primarily serves the frontend and recommendation service. A simple / demo page is included for local testing.

---

## TL;DR — get it running in 60 seconds

Make sure MongoDB is running locally, then from the `checkin-service/` directory:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

The API is on `http://localhost:5001`. Room data is seeded automatically on first startup.

---

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/rooms` | List all rooms with current crowd/quiet snapshot |
| `POST` | `/api/checkins` | Submit a new check-in report |
| `GET` | `/api/checkins/<user_id>` | Get all check-ins for a specific user |

---

### `POST /api/checkins`

**Request body (JSON):**

| Field | Type | Notes |
| --- | --- | --- |
| `user_id` | string | ID of the user submitting the report |
| `room_id` | string | Must match an existing room `_id` |
| `crowdedness` | int `[1, 5]` | 1 = empty, 5 = packed |
| `quietness` | int `[1, 5]` | 1 = noisy, 5 = silent |

**Example request:**

```bash
curl -X POST http://localhost:5001/api/checkins \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "room_id": "bobst_ll1", "crowdedness": 2, "quietness": 4}'
```

**Example response (`201`):**

```json
{
  "message": "Check-in created successfully",
  "checkin": {
    "_id": "664a1f...",
    "user_id": "u1",
    "room_id": "bobst_ll1",
    "time": "2026-05-02T18:30:00.000000",
    "crowdedness": 2,
    "quietness": 4
  }
}
```

On success the service also updates `current_crowd`, `current_quiet`, and `last_updated` on the room document so consumers always read fresh data.

---

### `GET /api/rooms`

Returns all rooms with their latest snapshot.

```bash
curl http://localhost:5001/api/rooms
```

```json
[
  {
    "_id": "bobst_ll1",
    "name": "Bobst LL1",
    "current_crowd": 2,
    "current_quiet": 4,
    "last_updated": "2026-05-02T18:30:00.000000"
  }
]
```

`current_crowd` and `current_quiet` are `null` until the first check-in is submitted for that room.

---

### `GET /api/checkins/<user_id>`

Returns all check-ins submitted by a user, newest first.

```bash
curl http://localhost:5001/api/checkins/u1
```

---

## Running locally

### Without Docker

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit if your MongoDB is not on localhost

python app.py                 # dev server on :5001 with autoreload
```

On first boot, four Bobst library rooms are seeded automatically if the `rooms` collection is empty.

### With Docker Compose

```bash
docker build -t checkin-service .
docker run -p 5001:5001 \
  -e MONGO_URI=mongodb://host.docker.internal:27017/ \
  checkin-service
```

---

## Tests

```bash
pytest --cov=. --cov-report=term-missing
```

---

## Configuration

All configuration is via environment variables. See [`.env.example`](./.env.example) for the full list.

| Variable | Default | Notes |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://localhost:27017/` | Connection string for MongoDB |
| `DB_NAME` | `nyu_library_app` | Database name (shared with other services) |
| `FLASK_ENV` | `development` | Set to `production` in prod |
| `PORT` | `5001` | Port the Flask server listens on |

---

## Database schema

Aligned with the schema agreed across the team:

- `rooms` — `{ _id, name, current_crowd, current_quiet, last_updated }`
- `checkins` — `{ _id, user_id, room_id, time, crowdedness, quietness }`

`crowdedness` and `quietness` are integers in `[1, 5]`. `time` is a UTC ISO-8601 string.

---

## Troubleshooting

**`pymongo.errors.ServerSelectionTimeoutError`** — MongoDB is not reachable. Make sure it is running and that `MONGO_URI` in `.env` points to the right host.

**`{"error": "Invalid room_id"}`** — the `room_id` you sent does not exist in the `rooms` collection. Call `GET /api/rooms` to see valid IDs, or restart the app to re-trigger the seed.

**`{"error": "Missing field: ..."}` or `400` on POST** — ensure the request body is valid JSON and includes all four required fields (`user_id`, `room_id`, `crowdedness`, `quietness`).

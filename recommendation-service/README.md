# Recommendation Service

Backend microservice that answers **"where should I go study right now?"** for the library crowdedness app. It reads room and checkin data from MongoDB, blends real-time community reports with historical patterns, and returns a ranked list of rooms as JSON.

This subsystem is consumed by the frontend; it is not user-facing.

---

## TL;DR — get it running in 60 seconds

Make sure Docker Desktop is running, then from the `recommendation-service/` directory:

```bash
make up      # build images and start API + MongoDB
make seed    # load sample data
make smoke   # hit every endpoint with curl
```

That's it. The API is on `http://localhost:8000`.

To stop everything: `make down`. To wipe the database too: `make clean`.

If you don't have `make` (Windows without WSL, etc.), run the equivalent docker commands listed in the [Makefile](./Makefile).

---

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/api/rooms` | List all rooms with their stored snapshot |
| `GET` | `/api/recommend` | Live + history blended ranking (Algorithm 1) |
| `GET` | `/api/forecast` | Weekday/hour bucket forecast (Algorithm 2) |

### `/api/recommend` query parameters

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `live_weight` | float `[0, 1]` | `0.7` | Weight on live data vs. history |
| `top` | int | _all_ | Return only the top N rooms |

### `/api/forecast` query parameters

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `weekday` | int `0..6` | now (UTC) | 0 = Monday |
| `hour` | int `0..23` | now (UTC) | |
| `top` | int | _all_ | Return only the top N rooms |

### Example response (`/api/recommend?top=2`)

```json
{
  "algorithm": "weighted",
  "live_weight": 0.7,
  "live_window_minutes": 30,
  "generated_at": "2026-05-02T18:30:00+00:00",
  "recommendations": [
    {
      "room_id": "bbst-5f",
      "name": "BBST 5F",
      "crowd": 1.64,
      "quiet": 4.14,
      "study_score": 8.5,
      "source": "history",
      "live_sample_size": 0,
      "history_sample_size": 14
    }
  ]
}
```

`study_score` is on a 0–10 scale (higher = better study spot). The `crowd` and `quiet` fields keep the original 1–5 scale used in checkin reports so the frontend can show them directly.

---

## Algorithms

**Weighted (`/api/recommend`)** — blends two averages: the mean of recent checkins (within `LIVE_WINDOW_MINUTES`) and the mean of all historical checkins. The mix is controlled by `live_weight`. If only one source has data, that source is used by itself; if neither has data, the configured defaults apply so every room is still rankable.

**Forecast (`/api/forecast`)** — buckets historical checkins by `(weekday, hour)`. For a target slot, the algorithm prefers the exact bucket, falls back to "any weekday at this hour" if the exact bucket has fewer than three samples, then to all history for that room, and finally to defaults. The `basis` field in each result tells the frontend which level was used.

---

## Database schema

Aligned with the schema agreed across the team:

- `rooms` — `{ _id, name, current_crowd, current_quiet, last_updated }`
- `checkins` — `{ _id, user_id, room_id, time, crowdedness, quietness }`
- `users` — `{ _id, username, password, display_name, created_at }` (read-only here; not currently used)

`crowdedness` and `quietness` are integers in `[1, 5]`. `time` is a UTC `datetime`.

---

## Running locally

### With Docker (recommended)

```bash
make up      # build + start API on :8000 and MongoDB on :27017
make seed    # populate sample rooms and ~200 historical checkins
make smoke   # curl every endpoint
make logs    # tail the API logs
make down    # stop the stack
make clean   # stop AND wipe the data volume
```

Equivalent without `make`:

```bash
docker compose up --build -d
docker compose run --rm seed
curl "http://localhost:8000/healthz"
curl "http://localhost:8000/api/recommend?top=3"
```

> **Note for zsh users (default on macOS):** wrap URLs that contain `?` and `&` in quotes, or zsh will try to glob-expand them. The Makefile already does this.

### Without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

# Make sure MongoDB is reachable at $MONGO_URI, then:
python scripts/seed_data.py                     # seed sample data
flask --app app.main:get_app run --debug        # dev server with autoreload

# Or production-style:
gunicorn --bind 0.0.0.0:8000 wsgi:application
```

---

## Tests

```bash
make test
# or
pytest
```

The suite enforces an 80 % coverage gate (see `pytest.ini`). Currently sits at **99 %** with **43** tests across the algorithms, the database layer, and the Flask endpoints (including failure paths).

---

## Configuration

All configuration is via environment variables. See [`.env.example`](./.env.example) for the full list with defaults and explanations.

The required ones for production are:

- `MONGO_URI` — the connection string for the shared cluster
- `MONGO_DB_NAME` — defaults to `library_app`

---

## Troubleshooting

**`Cannot connect to the Docker daemon`** — Docker Desktop isn't running. On macOS: `open -a Docker`, then wait until the whale icon stops animating.

**`zsh: no matches found: http://...`** — zsh is treating `?` as a glob. Quote your curl URLs (`"http://..."`) or run `setopt no_nomatch` in your shell.

**`service "recommendation" is not running`** — you ran `docker compose exec` before `docker compose up`. Start the stack first with `make up` (which uses `-d` so it returns immediately).

**`{"rooms": []}` and empty recommendations** — the database is empty. Run `make seed`.

**Tests pass locally but the container build fails** — clear the build cache: `make clean && make up`.

**Need to reset everything from scratch** — `make clean && make up && make seed`.

# Library Crowdedness — NYU Bobst
[![release](https://img.shields.io/github/v/release/swe-students-spring2026/5-final-design_ants-2)](https://github.com/swe-students-spring2026/5-final-design_ants-2/releases)
[![checkin-service](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/checkin-service.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/checkin-service.yml)
[![recommendation-service](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/recommendation-service.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/recommendation-service.yml)
[![webapp](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/webapp.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/webapp.yml)
[![CD (dev)](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/deploy.yml/badge.svg?branch=dev)](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/deploy.yml?query=branch%3Adev)
[![CD (prod)](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/deploy.yml/badge.svg?branch=prod)](https://github.com/swe-students-spring2026/5-final-design_ants-2/actions/workflows/deploy.yml?query=branch%3Aprod)

A web app for finding the best place to study in NYU's Bobst library. Students report how crowded and quiet each floor is, and the system blends those live reports with historical patterns to rank rooms by "study-ability".

## Team

- [Roger](https://github.com/DaobaRoger12)
- [Zelu Zhang](https://github.com/zzl0720-2025)
- [William Zhang](https://github.com/Incrediblez7)
- [Mumu Li](https://github.com/n3xta)
- [Haoze(Frank) Wu](https://github.com/HandEater)

## Architecture

Four services orchestrated by Docker Compose:

| Service | Purpose |
| --- | --- |
| `webapp` | User-facing UI |
| `checkin-service` | Accepts check-ins, exposes rooms API |
| `recommendation-service` | Ranks rooms (live + forecast) |
| `mongodb` | Shared persistence |

Each Python service has its own `Dockerfile`, its own test suite, and its own GitHub Actions workflow under [`.github/workflows/`](.github/workflows/).

## Container images

Published on Docker Hub:

- [incrediblez7/5-final-design_ants-checkin on Docker Hub](https://hub.docker.com/r/incrediblez7/5-final-design_ants-checkin)
- [incrediblez7/5-final-design_ants-recommendation on Docker Hub](https://hub.docker.com/r/incrediblez7/5-final-design_ants-recommendation)
- [incrediblez7/5-final-design_ants-webapp on Docker Hub](https://hub.docker.com/r/incrediblez7/5-final-design_ants-webapp)


## Quick start

Prerequisites: Docker Desktop running, and a clone of this repo.

```bash
# 1. Clone the repo
git clone https://github.com/swe-students-spring2026/5-final-design_ants-2.git
cd 5-final-design_ants-2

# 2. Create the env files (see "Configuration" below for what to fill in)
cp checkin-service/.env.example checkin-service/.env
cp recommendation-service/.env.example recommendation-service/.env

# 3. Build and start everything
docker compose up --build
```

Once the stack is up, open the webapp at **http://localhost:3000**. The check-in API is exposed on `5000` and the recommendation API on `8000`. MongoDB is mapped to host port `27019` (container `27017`).

To stop everything: `docker compose down`. To wipe persistent data too: `docker compose down -v`.

## Seed data

The app expects a `rooms` collection in MongoDB. Two helper scripts are provided:

```bash
# Minimal: just insert the rooms list (idempotent — skips if already populated)
docker compose exec checkin-service python -m db.seed_data

# Full: drops and reseeds rooms + 200 randomized historical check-ins
docker compose exec recommendation-service python scripts/seed_data.py
```

Run one of these once after the first `docker compose up`.

## Tests

Each service has its own pytest suite. Run them inside their containers:

```bash
docker compose exec checkin-service pytest
docker compose exec recommendation-service pytest
```

CI runs the same suites with coverage on every push / pull request.

## Configuration

Each service reads its config from environment variables. Defaults work for the bundled Docker Compose setup; override in `.env` files when running outside Docker or pointing at a remote MongoDB.

### `checkin-service/.env.example`

| Variable | Default | Notes |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://mongodb:27017/` | Use `mongodb://localhost:27019/` if running this service outside Docker |
| `DB_NAME` | `nyu_library_app` | Shared with recommendation-service |
| `PORT` | `5000` | |
| `GOOGLE_CLIENT_ID` | _(dummy)_ | Required only if Google OAuth login is enabled |
| `GOOGLE_CLIENT_SECRET` | _(dummy)_ | Same as above |
| `GOOGLE_REDIRECT_URI` | `http://localhost:3000/session/oauth/callback` | Must match an authorized redirect URI in your Google Cloud OAuth client |

### `recommendation-service/.env.example`

| Variable | Default | Notes |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://localhost:27017/` | Compose overrides to `mongodb://mongodb:27017/` |
| `DB_NAME` | `nyu_library_app` | Must match checkin-service |
| `LIVE_WINDOW_MINUTES` | `30` | A check-in is "live" if newer than this |
| `LIVE_WEIGHT` | `0.7` | Blend weight on live signal vs. history (0–1) |
| `DEFAULT_CROWD` | `3.0` | Fallback when no data exists |
| `DEFAULT_QUIET` | `3.0` | Fallback when no data exists |

The `webapp` service shares `checkin-service/.env` (it needs the same Google OAuth credentials to render the login flow). It does not have its own `.env.example`.

## Branches & deployment

- `main` — stable integration branch
- `dev` — pushes here trigger the `deploy.yml` workflow that builds, pushes images to Docker Hub, and deploys to the dev environment
- `prod` — production branch; deploys behind `lock-in.space`

## License

See [LICENSE](./LICENSE).
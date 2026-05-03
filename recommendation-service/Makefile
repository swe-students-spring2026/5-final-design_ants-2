# Common dev commands for the recommendation service.
#
# Usage: run any of these from the recommendation-service/ directory.
#
#   make up        - build images and start API + MongoDB in the background
#   make seed      - load sample data into MongoDB (run after `make up`)
#   make logs      - tail the API container logs (Ctrl-C to detach)
#   make smoke     - hit every endpoint with curl as a quick sanity check
#   make test      - run pytest with coverage gate (no Docker needed)
#   make down      - stop the stack but keep the data volume
#   make clean     - stop AND wipe the data volume
#   make rebuild   - down + clean + up --build (use after Dockerfile edits)

.PHONY: up seed logs smoke test down clean rebuild

up:
	docker compose up --build -d
	@echo ""
	@echo "API:    http://localhost:8000"
	@echo "Mongo:  mongodb://localhost:27017"
	@echo "Run 'make seed' to load sample data."

seed:
	docker compose run --rm seed

logs:
	docker compose logs -f recommendation

smoke:
	@echo "→ /healthz"
	@curl -s "http://localhost:8000/healthz" && echo ""
	@echo "→ /api/rooms"
	@curl -s "http://localhost:8000/api/rooms" && echo ""
	@echo "→ /api/recommend?top=3"
	@curl -s "http://localhost:8000/api/recommend?top=3" && echo ""
	@echo "→ /api/forecast?weekday=2&hour=14&top=3"
	@curl -s "http://localhost:8000/api/forecast?weekday=2&hour=14&top=3" && echo ""

test:
	pytest

down:
	docker compose down

clean:
	docker compose down -v

rebuild: clean
	docker compose up --build -d

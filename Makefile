# Canonical task interface (CI + Linux/macOS/containers).
# Windows without make: run the underlying uv/docker commands directly.

.PHONY: dev down test lint eval seed replay demo export migrate

dev:  ## bring up db + hot-reload api (host) — architecture.md "dev = prod"
	docker compose -f infra/docker-compose.yml up -d db
	cd backend && uv run alembic upgrade head
	cd backend && uv run uvicorn evermind.api.main:app --reload

down:
	docker compose -f infra/docker-compose.yml down

migrate:  ## apply pending Alembic migrations
	cd backend && uv run alembic upgrade head

test:  ## L0 + L1 + L3 — deterministic, no network (testing-strategy.md)
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check .
	cd backend && uv run lint-imports

eval:  ## L2 extraction eval — make eval-live / eval-recorded lands in P2
	@echo "make eval lands in P2 (OPS-3 eval harness)" && exit 1

seed:  ## load data-v2/org.json into the org tables
	cd backend && uv run python -m evermind.org.seed ../data-v2/org.json

replay:  ## paced replay of data-v2/corpus.jsonl (demo beat)
	cd backend && uv run python -m evermind.connectors.replay ../data-v2/corpus.jsonl

demo:  ## full compose + seed + instant replay — the L4 smoke shape
	docker compose -f infra/docker-compose.yml up -d
	$(MAKE) seed
	REPLAY_PACE_MS=0 $(MAKE) replay

export:  ## CSV/JSON export of decisions/tasks/digests — the handoff story
	@echo "make export lands in P7 (deploy runbook)" && exit 1

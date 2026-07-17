# Canonical task interface (CI + Linux/macOS/containers).
# Windows without make: run the underlying uv/docker commands directly (see README).

.PHONY: db db-down api test lint eval

db:  ## start local Postgres (schema auto-applied from infra/schema.sql)
	docker compose -f infra/docker-compose.yml up -d db

db-down:
	docker compose -f infra/docker-compose.yml down

api:  ## run the FastAPI dev server
	uv run uvicorn backend.app.main:app --reload

test:  ## fast suite: deterministic, no network, LLM mocked
	uv run pytest -q

lint:
	uv run ruff check .

eval:  ## extraction golden-set eval — real DeepSeek calls (F6)
	@echo "make eval lands in Phase 1 (F6 eval harness)" && exit 1

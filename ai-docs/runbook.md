# Runbook — bringing the EverMind stack up

> Everything runs in Docker: Postgres (pgvector), the FastAPI backend, the Next.js
> dashboard. No local Python or Node needed — dev tooling runs inside the api
> container too. Verified end to end on 2026-07-18 (main @ PR #44).

## Prerequisites

- Docker Desktop running (compose v2).
- One-time: create the env file (git-ignored; defaults work — `AI_API_KEY` only
  matters once extraction lands):

  ```sh
  cp infra/.env.example infra/.env
  ```

## 1 · Start the stack

```sh
docker compose -f infra/docker-compose.yml up -d --build
```

First build takes a few minutes (api installs locked deps, frontend runs `npm ci`).
The api container runs `alembic upgrade head` on start, then uvicorn with reload;
both api and frontend **bind-mount the source**, so code edits hot-reload without
rebuilding. Rebuild (`--build`) only when `pyproject.toml`/`uv.lock` or
`package.json`/`package-lock.json` change.

Check it's alive:

```sh
docker compose -f infra/docker-compose.yml ps
curl http://localhost:8000/healthz        # {"status":"ok"}
```

| Surface | URL |
|---|---|
| Dashboard | http://localhost:3000 (`/tasks`, `/feed`, `/blockers`, `/digest`, `/upload`) |
| API docs (Swagger) | http://localhost:8000/docs |
| API | http://localhost:8000 — every request needs header `X-Persona: <handle>` (e.g. `linh`; handles come from `GET /personas`) |

## 2 · Load the demo data

`data-v2/` is not mounted into the container — copy the two files in, then run the
CLIs (they are idempotent; re-running never duplicates):

```sh
docker cp data-v2/org.json    infra-api-1:/tmp/org.json
docker cp data-v2/corpus.jsonl infra-api-1:/tmp/corpus.jsonl

docker compose -f infra/docker-compose.yml exec -T api \
  python -m evermind.org.seed /tmp/org.json

# instant replay (demo/L4 shape); drop the env override for the paced demo beat (800ms/msg)
docker compose -f infra/docker-compose.yml exec -T -e REPLAY_PACE_MS=0 api \
  python -m evermind.connectors.replay /tmp/corpus.jsonl /tmp/org.json
```

> **git-bash on Windows:** prefix these with `export MSYS_NO_PATHCONV=1` (or use
> PowerShell) — otherwise `/tmp/...` args get rewritten to Windows paths before
> they reach the container.
>
> **Frontend edits on Windows:** Next's file watcher doesn't see host edits
> through the bind mount — after changing FE code, run
> `docker compose -f infra/docker-compose.yml restart frontend` to recompile.

After this: 9 users in the persona switcher data, 118 messages captured across
both groups (`GET /health/capture` shows both alive).

## 3 · What works today vs. not yet

Writes go through `POST /commands` (the D3 gateway — propose/approve/reject,
task updates, signals). **Known P4-glue gaps** (tracked in the PR #42/#44 reviews):

- The projection-consumer loop is **not wired into the app** — a command appends
  `domain_events`, but the board only updates after the consumer folds them. To
  fold manually:

  ```sh
  docker compose -f infra/docker-compose.yml exec -T api python -c \
    "from evermind.db.session import SessionLocal; from evermind.tasks.consumer import TasksConsumer
  s = SessionLocal(); print(TasksConsumer(s).poll_and_apply(), 'events folded'); s.commit()"
  ```

- The scheduler (radar sweep, capture self-check) is defined but not started.
- The FE persona switcher isn't wired to `/personas` yet — dashboard pages render
  live read data but not per-persona feeds.
- No extraction yet (ING is Lane A's P2) — replayed chat doesn't become
  decisions/tasks on its own; decisions enter via `POST /commands`.

## 4 · Tests & linters (inside the container)

Dev tools aren't in the image (runtime deps only) — install once per container
lifetime, and give the tests the fixtures:

```sh
docker cp data-v2 infra-api-1:/data-v2      # tests resolve ../data-v2 from /app
docker compose -f infra/docker-compose.yml exec -T api \
  pip install -q pytest pytest-asyncio ruff mypy import-linter
docker compose -f infra/docker-compose.yml exec -T api python -m pytest -q
docker compose -f infra/docker-compose.yml exec -T api sh -c "ruff check . && mypy evermind && lint-imports"
```

⚠️ The test suite **wipes every table** per test (isolation by design) — re-run
step 2 afterwards to restore demo data.

## 5 · Reset / stop

**Standing rule until P7:** migration `0001` is `create_all` over the live models,
so after any schema change an existing DB silently misses new tables — **reset,
don't hope**:

```sh
# full reset (drops the volume), then re-migrate + re-load data
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d --build
# api re-runs alembic on start; then redo step 2

# faster reset keeping containers up:
docker compose -f infra/docker-compose.yml exec -T db \
  psql -U evermind -d evermind -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose -f infra/docker-compose.yml exec -T api alembic upgrade head
```

Stop without losing data: `docker compose -f infra/docker-compose.yml down`.

## 6 · Prod profile (untested)

`docker compose -f infra/docker-compose.yml --profile prod up -d` adds Caddy on
80/443 (`infra/Caddyfile`). Not yet exercised — part of P7's deploy runbook work.

## 7 · Frontend on Vercel (placeholder mode)

The designed deployment is the VPS/compose one above; Vercel hosts the
**frontend only** (the FastAPI monolith + scheduler + Postgres is not
serverless-shaped). Import via the Vercel UI:

1. **Add New → Project** → import `qdgiang/EverMind`.
2. **Root Directory: `frontend`** — the one setting that matters; framework
   auto-detects as Next.js, `frontend/vercel.json` pins the `sin1` region.
3. **Environment variables: none** for placeholder mode — SSR fetches fail
   fast and every page renders its designed empty state. (Contract:
   `frontend/.env.example`.)
4. Deploy. Every push to `main` redeploys production; PRs get preview URLs.

To make it live later: host the API publicly (VPS profile above), then set
`NEXT_PUBLIC_API_URL` **and** `API_URL_INTERNAL` to its URL in the Vercel
project settings and redeploy. Browser-side writes (upload, command client)
additionally need CORS middleware on the API — tracked follow-up; SSR reads
work without it.

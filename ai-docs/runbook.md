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
task updates, signals). The read side runs itself: the in-app consumer loop
(`CONSUMER_POLL_MS`, default 2s) folds `domain_events` into tasks + signals +
surfacing, and APScheduler runs the radar sweep, capture self-check, LLM
extraction beat (`EXTRACTION_INTERVAL_SEC`), and the SIG-1 **promotion beat**
(`PROMOTION_SWEEP_SEC`, default 60s).

The weak-signal pipeline (the signature feature) is live end to end: extraction
drafts weak signals alongside decisions → `RecordSignal` through the gateway →
ledger → promotion (≥2 corroborating mentions, or 1 + staleness) → mentions
flip to `promoted` (they are the board card, citations = every mention) → a
task-linked promotion also submits a **PROPOSED** blocked-state decision in the
first mention author's name — a human confirms it, then the fold writes the
blocked status + counterparty context the `/blockers` board groups by.

Still open: asks/parked digest aging (G35), dependency-derived lamps (G16),
reaction capture (interface #8), FE persona-switcher polish.

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

To make it live later: host the API publicly (VPS profile above, **or ngrok —
next section**), then set `NEXT_PUBLIC_API_URL` **and** `API_URL_INTERNAL` to
its URL in the Vercel project settings and redeploy. The API ships CORS
(`allow_origins=["*"]`, no credentials — demo-honest per settled #3), so
browser-side writes work cross-origin.

### Vercel → local stack via ngrok

Point the deployed FE at the compose stack on this machine:

1. Local stack up + data loaded (§1–2), then tunnel the API:

   ```sh
   ngrok http 8000
   ```

2. Copy the `https://….ngrok-free.app` URL into the Vercel project →
   **Settings → Environment Variables**, as BOTH `NEXT_PUBLIC_API_URL` and
   `API_URL_INTERNAL` → **Redeploy**.
3. Done — the vercel.app pages now render this machine's live data.

Notes: free-tier ngrok URLs change on every restart (reserve your free static
domain in the ngrok dashboard to avoid re-setting env + redeploying each
time); the api-client already sends `ngrok-skip-browser-warning` so browser
calls bypass ngrok's interstitial page; the tunnel exposes the
unauthenticated demo API to anyone with the URL — run it only while demoing.

## 8 · Telegram live capture (CAP-4)

Read-only by design (settled #20): the bot only ever **reads** the group. The
poll loop starts with the api (lifespan) as soon as a bot token is configured;
`TELEGRAM_POLL_MS=0` disables it. Bots can never see messages sent before they
joined — history/backfill is replay's job (CAP-2).

### One-time bot setup (in Telegram, human steps)

1. BotFather → `/newbot` → copy the token.
2. BotFather → `/setprivacy` → **Disable** — *before* the bot joins the group,
   otherwise it only receives `/slash` commands and nothing else.
3. Create the demo group and add the bot as a member. Tip: set **Chat history
   for new members → Visible** right away — this upgrades the group to a
   supergroup *now*, so its chat id is the stable `-100…` form and never hits
   the `migrate_to_chat_id` remap case mid-demo.

### Wire it to the stack

1. Token → `infra/.env`:

   ```sh
   TELEGRAM_BOT_TOKEN=123456:ABC-your-token
   # TELEGRAM_POLL_MS=2000   # optional; 0 disables the loop
   ```

   `.env` is injected via compose `env_file`, so a plain `restart` won't pick
   it up — recreate the container:

   ```sh
   docker compose -f infra/docker-compose.yml up -d --force-recreate api
   ```

2. Discover the group's chat id: send any message in the group, then

   ```sh
   docker compose -f infra/docker-compose.yml logs api | grep "not mapped"
   # → "telegram chat -100123456789 is not mapped in chat_groups — …"
   ```

   (Unmapped messages are still captured, with `group_id NULL`.)

3. Fill the placeholders in `data-v2/org.json` (the seed **skips** any value
   still starting with `FILL_ME`):
   - `G-LIVE.platform_chat_id` → the chat id from the log line.
   - each demo member's `identities` entry → their **numeric Telegram user id**
     (the load-bearing [D5] key — resolution prefers it because usernames are
     mutable and may differ from what anyone remembers; a username entry is an
     optional extra). Senders with no identity row become **provisional users**
     (G44) joined to the group's team; the lead confirms them from the
     workspace.

4. Re-copy + re-seed (idempotent):

   ```sh
   docker cp data-v2/org.json infra-api-1:/tmp/org.json
   docker compose -f infra/docker-compose.yml exec -T api \
     python -m evermind.org.seed /tmp/org.json
   ```

   No api restart needed — the poll loop rebuilds the chat-id → group map from
   the DB every beat.

### Verify the demo beat

Post `!blocked thiếu 20 đèn lồng` in the group. Within ~2 s (`TELEGRAM_POLL_MS`):
the message lands in `messages`, the marker materializes a blocked task through
`POST /commands`' gateway path, and it shows in the **Đêm hội Trăng Rằm — Live**
workspace with the message as its evidence citation. `GET /health/capture` now
lists the group. Message edits append `message_revisions` (G45) — the citation's
`rev_at_capture` keeps pointing at the original wording.

Restart safety: the `getUpdates` offset is held in memory; after an api restart
Telegram re-delivers unacknowledged updates and the connector drops the
duplicates by `raw_ref`. Nothing is double-captured.

## 9 · LLM extraction (ING) — decisions/tasks from plain chat

Every `EXTRACTION_INTERVAL_SEC` (30, `0` = off) the scheduler cuts a
window per **live-platform group** (telegram; the seeded replay corpus is
deliberately excluded from the automatic beat): up to `EXTRACTION_BATCH_SIZE`
(20) unprocessed messages, but only once the newest one is
`EXTRACTION_SETTLE_SEC` (120) seconds old — an actively-flowing conversation
is never cut mid-thought. The window goes to the configured LLM (`AI_BASE_URL` /
`AI_MODEL` — DeepSeek) with org context (members, open tasks, party aliases);
extracted candidates enter through the SAME command gateway as everything
else: confidence < `CONFIDENCE_TAU` (0.8) ⇒ born proposed, and the authority
gate applies regardless — a member's extracted decision waits for the lead
exactly like a marker would. `!marker` messages are the deterministic lane's
property and are skipped.

Demo "extract now" button (don't wait out the interval on stage):

```sh
curl -X POST -H "X-Persona: minhpq" "http://localhost:8000/ingestion/extract"
# or one group only:  ...:8000/ingestion/extract?group_id=<chat_groups.id>
```

Bookkeeping: `extraction_windows` (one row per window: status, attempts,
token spend), `ingest_cursors` (per-group high-water mark, EPOCH SECONDS of
the last processed message ts — advances only when a window's outputs
persist, so an `LLM unavailable` window retries the same messages next beat
and nothing is ever skipped). Re-extraction after a lost cursor dedups via
`materializations` — no duplicate decisions.

# EverMind

**Ambient institutional memory + decision-driven coordination for a volunteer NPO.** The
bot listens where the team already talks (group chat, meeting transcripts) — and never
speaks. Conversation becomes an append-only, cited graph of **decisions** that drive
**tasks**; the org's own authority structure decides what becomes real; everything the
system knows surfaces on a dashboard: per-persona feeds, approver inboxes, team digests,
blocker radar, and answers-with-receipts.

## State of the repo (2026-07-18)

**Design: done.** `ai-docs/design-v2.md` rev 13, hardened by 48 adversarial scenario traces
(gap register G1–G69) and 23 resolved debates. **Code: P0 scaffold in place** —
`backend/evermind/<module>/{models.py,service.py}` for every module in
`ai-docs/architecture.md`'s layout, migration 0001, docker-compose, and a Next.js
frontend shell (styled after `frontend_ref/`) all exist but are mostly `TODO`/`STUB`
bodies. Two people build in parallel from here per
[`ai-docs/work-split.md`](ai-docs/work-split.md) — module ownership (A/B), phase
order, and the 9 A↔B interfaces are frozen there; **Claude is the merge gate**.

```sh
uv sync --project backend --all-extras --dev   # or: cd backend && uv sync --all-extras --dev
cd backend && uv run pytest -q                 # L0 fixture tests — 7 passing
docker compose -f infra/docker-compose.yml up -d db
cd backend && uv run alembic upgrade head       # creates every table in data-model.md
```

## Start here

| You want to… | Read |
|---|---|
| Understand the product | [`ai-docs/VISION.md`](ai-docs/VISION.md) · [`PROBLEM_STATEMENT.md`](PROBLEM_STATEMENT.md) |
| Know the business rules | [`ai-docs/design-v2.md`](ai-docs/design-v2.md) (**the** source of truth) |
| Build it | [`ai-docs/README.md`](ai-docs/README.md) — reading order: features → architecture → data-model → testing-strategy → plan |
| See the proof it holds up | [`ai-docs/scenarios/`](ai-docs/scenarios/) · [`ai-docs/debates/`](ai-docs/debates/) |
| Demo/eval fixtures | [`data-v2/`](data-v2/) (corpus + hand-verified answer key + org seed) |

## The five rules that define the system

1. Decisions are the write path; **tasks are a projection** (fold of effective decisions + PIC updates).
2. **Append-only**: a decision's body never changes; only its status flips (supersession, sweep, resurrection).
3. **Proposals never expire** — only a human act changes a status; clocks only create visibility.
4. **The bot never posts to groups** — read-only capture; all output on the dashboard; humans relay.
5. **Precision >> recall**, receipts everywhere: every extracted record cites its source messages.

## Layout

```
backend/evermind/   FastAPI modular monolith — contracts · org · llm · connectors ·
                     ingestion · decisions · tasks · signals · surfacing · knowledge ·
                     api · scheduler · db   (Postgres 16 + pgvector)
backend/migrations/  Alembic; 0001 = the full data-model.md schema
frontend/            Next.js dashboard (persona switcher — no login in demo),
                     shell ported from frontend_ref/
frontend_ref/         standalone HTML/JS/CSS visual reference — not shipped code
infra/               docker-compose (dev = prod), Caddy for VPS TLS
data-v2/             fixtures (corpus + hand-verified answer key + org seed)
ai-docs/             all of the above documentation
```

Everything self-hostable: `docker compose up` is the deployment story.

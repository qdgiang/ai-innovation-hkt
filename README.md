# ai-innovation-hkt

**EverMind** — ambient institutional memory and decision-driven coordination for a
volunteer NPO (48h hackathon build). It listens where the team already talks (group
chat + meeting transcripts), turns conversation into an append-only, cited graph of
**decisions** that drive **tasks**, and serves the memory back as per-team digests,
answers-with-receipts, blocker radar, and onboarding briefs — with the org's own
authority structure deciding what becomes real.

**Start here: [`ai-docs/VISION.md`](ai-docs/VISION.md)** (the full picture) ·
design source of truth: [`ai-docs/design-v2.md`](ai-docs/design-v2.md) (rev 9) ·
verification: [`ai-docs/scenarios/`](ai-docs/scenarios/) (43 traces, gap register) ·
demo/eval fixtures: [`data-v2/`](data-v2/). ⚠ `ai/schemas.py` still reflects the v1
contracts and is superseded by design-v2 until rebuilt.

## Layout

| Path | What |
|------|------|
| `ai/` | AI layer — frozen contracts (`schemas.py`), extraction, markers, Q&A, digest. Pure functions, no DB writes. |
| `backend/` | FastAPI service — persistence, REST API, scheduling. No prompts, no LLM SDK. |
| `ingestion/` | Adapters — replay corpus, meeting transcripts, Telegram bot (Phase 2). |
| `data/` | Synthetic corpus + answer key + golden set (the demo/eval fixtures). |
| `infra/` | docker-compose (Postgres 17 + canonical DDL), deploy config. |
| `frontend/` | Next.js dashboard (initialized in Phase 3). |
| `tests/` | Fast suite — deterministic, no network. |

## Quickstart

```sh
uv sync                # install deps (Python >= 3.12)
uv run pytest -q       # fast suite
make db                # local Postgres w/ schema (docker compose up -d db)
make api               # FastAPI dev server → http://localhost:8000/healthz
```

Windows without `make`: run the underlying commands from the [Makefile](Makefile)
directly (`docker compose -f infra/docker-compose.yml up -d db`, etc.).

Copy `.env.example` to `.env` for configuration; variable names are contract
(see `ai-docs/deployment.md`).

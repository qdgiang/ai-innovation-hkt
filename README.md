# ai-innovation-hkt

**OrgMemory** — ambient org memory for a volunteer NPO (48h hackathon build).
Passive capture from Telegram + meeting transcripts → LLM extraction into typed,
cited records (decision / blocker / status) → weekly digest, cited Q&A, blocker
alerts, onboarding briefs. Planning docs live in [`ai-docs/`](ai-docs/).

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

# EverMind

**Ambient institutional memory + decision-driven coordination for a volunteer NPO.** The
bot listens where the team already talks (group chat, meeting transcripts) — and never
speaks. Conversation becomes an append-only, cited graph of **decisions** that drive
**tasks**; the org's own authority structure decides what becomes real; everything the
system knows surfaces on a dashboard: per-persona feeds, approver inboxes, team digests,
blocker radar, and answers-with-receipts.

## State of the repo (2026-07-18)

**Design: done.** `ai-docs/design-v2.md` rev 13, hardened by 48 adversarial scenario traces
(gap register G1–G69) and 23 resolved debates. **Code: reset.** The early scaffold was
deleted once the business logic outgrew it — implementation restarts from
[`ai-docs/plan.md`](ai-docs/plan.md) phase P0 against a clean spec.

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

## Planned layout (built in plan P0)

```
backend/    FastAPI modular monolith — connectors · ingestion · decisions · tasks ·
            signals · surfacing · knowledge · api  (Postgres 16 + pgvector)
frontend/   Next.js dashboard (persona switcher — no login in demo)
infra/      docker-compose (dev = prod), Caddy for VPS TLS
data-v2/    fixtures (already present)
ai-docs/    all of the above documentation
```

Everything self-hostable: `docker compose up` is the deployment story.

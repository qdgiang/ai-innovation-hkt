# EVM-021 — Prevent stale dashboard writes from overwriting chat state

> Priority: P0 · Status: `OPEN`

## Problem

A dashboard form can be opened from an old projection while a chat decision changes the same
facet. Submitting the stale form must not silently supersede newer context.

## Options

- **Option A — Last submitted write wins:** familiar but unsafe and hides cross-surface conflict.
- **Option B — Optimistic command versioning (`PROPOSED`):** include expected resource/facet version and
  client command ID; show a diff and require reconfirmation on mismatch.
- **Option C — Lock resources while edited:** prevents conflict but is brittle for asynchronous chat and
  long-lived browser sessions.

## Acceptance criteria

- A stale dashboard command cannot overwrite a newer facet without explicit reconfirmation.
- Double-click/retry with one command ID produces one domain event.
- The accepted command still passes current authorization and terminal-state checks.
- Successful writes use domain event → projection → outbox; they are never fake-ingested messages.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — FIX; Option B adopted (rev-14 absorption queue).** Real cross-surface race with a
cheap, standard answer: every dashboard command carries the expected unit version (the current
same-unit effective decision id, or the task's last event id) plus a client command id. Version
mismatch → the G52 diff card ("this changed since you opened the form") and explicit
reconfirmation — a stale form can never silently supersede a newer chat decision. The command
id makes retries/double-clicks idempotent (one domain event), riding the same upsert-by-key
machinery windows already use. Accepted commands still pass authorization and terminal-state
checks at accept time (G52). Acceptance criteria adopted with one amendment: the pipeline is
domain event → projection → **dashboard feed** — the outbox leg died with settled #20 — and
dashboard writes are never fake-ingested messages (aligned with D3). Option C locks rejected.

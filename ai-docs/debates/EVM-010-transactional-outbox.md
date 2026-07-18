# EVM-010 — Make outbound notifications transactional and idempotent

> Priority: P1 · Status: `OPEN`

## Problem

A domain change may commit while its chat announcement is lost, or a retry may send duplicates.
The outbound registry alone does not close the transaction boundary.

## Options

- **Option A — Best-effort send after commit:** simple but permits silent notification loss.
- **Option B — Transactional outbox (`PROPOSED`):** persist event and outbox together, retry with an
  idempotency key, and register the platform message after delivery succeeds.
- **Option C — Include platform send in the database transaction:** not a real atomic boundary and can
  hold database transactions across network failures.

## Acceptance criteria

- A crash after domain commit cannot lose the pending notification.
- Retrying after uncertain delivery does not create duplicate logical announcements.
- The outbound registry receives the platform message ID only after successful send.
- Persistent delivery failure is visible without reverting already-effective domain truth.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — MOOT; superseded by settled #20.** This issue's premise — the bot announces
domain changes into chat — no longer exists: the bot never posts to groups, and the outbound
registry is retired. All notification surfaces are dashboard projections (feed entries, inbox
items) derived from domain events inside the same database — transactionally consistent by
construction, no distributed send boundary, nothing to lose or duplicate. What survives:
(a) the honesty criterion lives on as the existing backlog-notice rule — degraded state is
always disclosed, never silent; (b) **Option B is pre-approved as the pattern** if outbound
chat delivery ever returns on the roadmap (e-mail/webhook connectors included) — persist event
+ outbox atomically, idempotency key per logical notification, register the platform message
id only after confirmed send. Parked, not needed for the build.

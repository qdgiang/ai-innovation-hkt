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

# EVM-002 — Prevent marker double materialization

> Priority: P0 · Status: `OPEN`

## Problem

A marker is materialized immediately but its message later appears in an extraction window. The
same human act can therefore create two semantic records.

## Options

- **Option A — Remove marker messages from extraction:** prevents duplicates but loses useful context.
- **Option B — Keep as `already_materialized` context (`PROPOSED`):** the extractor may cite/use the
  message but may not emit the already-created semantic record.
- **Option C — Deduplicate only after extraction:** preserves context but wastes extraction and leaves a
  larger correctness surface.

## Acceptance criteria

- A marker command creates one record even after window replay/retry.
- Idempotency includes source message, command index, record kind, and target/facet.
- Multiple marker commands in one message remain independently addressable.
- Grace-window edits amend the existing marker record and append revision history.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — FIX; Option B adopted (rev-14 absorption queue).** Genuine gap — the one real
double-materialization path the 48-scenario register missed. Rule: marker messages enter their
window's transcript labeled `already_materialized` — citable context, but the extractor may not
re-emit the record the marker already created; the write path backstops with the existing
window idempotence machinery, extending the dedup key to (source_message_id, command_index,
kind, unit). Criterion 4 is already covered today (the ~10-min grace lane amends, G45); the
multi-command-per-message criterion rides the command_index. Design-text absorption happens in
the next design pass — this file records the chosen option.

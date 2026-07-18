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

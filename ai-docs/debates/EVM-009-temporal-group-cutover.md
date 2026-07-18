# EVM-009 — Specify temporal group cutover

> Priority: P1 · Status: `OPEN`

## Problem

The same chat group may be reused for a new season. A permanent binding contradicts that reality,
while an unversioned remap makes late delivery and archive references ambiguous.

## Options

- **Option A — Require a new group per project:** simple but conflicts with established NPO behavior.
- **Option B — Temporal group bindings (`PROPOSED`):** flush, atomically close/open bindings, and route by
  event time with explicit archive handling.
- **Option C — Choose project per message:** flexible but imposes constant classification/triage burden.

## Acceptance criteria

- Partial extraction windows flush before cutover.
- A pre-cutover message delivered late remains in the old project.
- Post-cutover chatter defaults to the new project.
- Replying to an old record opens archive context but cannot silently revive/modify a closed task.
- Imports require an explicit project scope.

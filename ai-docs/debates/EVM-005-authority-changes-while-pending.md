# EVM-005 — Revalidate authority while proposals are pending

> Priority: P0 · Status: `OPEN`

## Problem

A proposal may wait while leads, memberships, delegations, or project ownership change. Checking
authority only when the proposal was created makes later approval unsafe.

## Options

- **Option A — Freeze creation-time authority:** deterministic but lets departed/reassigned approvers act.
- **Option B — Revalidate at every authority act (`PROPOSED`):** reroute pending work after org changes
  and snapshot the authority used by effective history.
- **Option C — Cancel every proposal on org change:** safe but discards useful work and creates churn.

## Acceptance criteria

- Approval uses current authority and current target state.
- Org changes reroute rather than silently drop pending proposals.
- Delegations are scoped and may expire.
- Removing a reaction or editing an approval reply creates a challenge/correction event, never a
  silent undo of effective history.

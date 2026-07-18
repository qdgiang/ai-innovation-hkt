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

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — COVERED; Option B is already rev 13's behavior.** The pieces landed across runs
6–9: approval-time revalidation re-checks the target's current state (G52); the approver's
rank is evaluated at the moment of the act, and the maker's rank is snapshotted
(`decided_by_role_at_time`); org changes reroute pending work (offboarding sweep re-routes
approvals; G62 mini-sweep for provisional holders); reaction removal files a challenge after
the grace window, never a silent undo (G67); an edit under an approval demotes to `proposed`
with a diff (G65). Delegation is per-utterance-cited — inherently scoped to that one decision;
general delegation grants with expiry remain §Deferred. One sentence to absorb in the next
design pass, for completeness: *authority is evaluated at act time and snapshotted on the act.*
Nothing else to change.

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

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — REJECTED; settled #13b stands (Option A, deliberately).** "One chat group ↔
exactly one project, permanently" is an explicit user ruling, not an oversight — temporal
bindings reintroduce precisely the remap ambiguity that ruling killed. New season = **new
group** mapped to the new project (S22 traced this clean; org config ops cover it; creating a
group is one tap for the org and zero ambiguity forever for the system). The residual
acceptance criteria are already covered without bindings: late messages fold by event `ts`
(G31) and their group's mapping is unambiguous; archive replies cannot revive closed tasks
(G52 terminal locks); imports carry project scope via their group. If a real deployment
insists on reusing one platform group across seasons, the adapter maps it to a new *logical*
group at cutover — an adapter concern under settled #13a, roadmap note only.

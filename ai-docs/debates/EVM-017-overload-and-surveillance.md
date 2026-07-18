# EVM-017 — Bound overload warnings without surveillance

> Priority: P2 · Status: `OPEN`

## Problem

Cross-team workload can reveal bottlenecks, but person-centric ranking or leaking inaccessible task
details can damage trust and violate project-scoped visibility.

## Options

- **Option A — Person productivity leaderboard:** easy to compare, harmful and not evidence of capacity.
- **Option B — Explainable workload-risk warning (`PROPOSED`):** warn rather than block, expose the input
  formula, allow correction, and aggregate hidden-project load without titles.
- **Option C — Remove person-level overload:** avoids surveillance but loses a real coordination signal.

## Acceptance criteria

- No productivity ranking or performance score is shown.
- Assigner and assignee can inspect/correct accessible inputs.
- Inaccessible project work contributes only an aggregate risk indicator.
- Warnings are advisory, attributable, and do not silently block assignment.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — COVERED, with the guardrails made explicit product rules.** Option B is rev 13's
overload design already: warn-don't-block; the formula is documented and explainable (per-day
overlapping windows across all the person's teams, urgent ×2, due-≤7d extra); inputs are
correctable through the normal lanes (date/assignment decisions, PIC updates); silence-past-X
= logged acceptance, attributable on the decision. Adopted as explicit rules going forward:
**no productivity ranking, leaderboard, or person-score view exists anywhere** — lamps and
flags attach to tasks and decisions, not to people as scores (settled #4 dropped the
anti-surveillance *framing*, not this line); and when read ACLs land (D8 roadmap),
inaccessible-project load contributes only an untitled aggregate. In the no-ACL demo that last
rule is vacuous. Option C rejected — the coordination signal is real and stays.

# EVM-018 — Keep G61/G64 accepted with revisit triggers

> Priority: P2 · Status: `ACCEPTED`

## Problem

Peer-lead decision churn (G61) and an explicit negotiation lifecycle state (G64) are real gaps, but
their fixes add tuned alerts and lifecycle/UI branches under the hackathon clock.

## Options

- **Option A — Implement both now:** closes the gaps but expands scope before core contracts exist.
- **Option B — Accept with observable triggers (`PREFERRED`):** keep documented workarounds and queries;
  revisit when real usage crosses an agreed threshold.
- **Option C — Remove the affected flows:** reduces scope but weakens honest proposal and peer-authority
  behavior.

## Acceptance criteria

- Both accepted gaps remain named in the spec and issue catalog.
- A query/runbook can identify repeated peer flips and stale negotiated proposals.
- Revisit thresholds and responsible owner are recorded before production rollout.
- Workarounds never present pending negotiation or peer churn as resolved truth.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — ACCEPTED (Option B confirmed), revisit triggers now concrete.** Both gaps stay
accepted under settled #15 with their recorded workarounds (design §Accepted gaps — which now
also holds G68-residual, same policy). Triggers, so "accepted ≠ forgotten" is checkable:
**G61** — revisit when any unit shows ≥3 effective flips within 14 days between rank-equal
actors; the runbook query is the documented one-GROUP-BY over `decisions` (unit, actor-rank,
14-day window). **G64** — revisit when pending proposals regularly accumulate ≥3 amendments or
long reply threads before approval (negotiation signature; visible in the aged pending queue).
**G68-residual** — revisit when foreign-routed proposals exceed a few per week (people
persistently deciding cross-room). Owner: the coordinator reviews these at each campaign
retrospective; thresholds get re-tuned on real usage before any production rollout. Note:
G64's workaround reverted to the dismiss-stale form — the renew-loop variant died with
proposal expiry (settled #18).

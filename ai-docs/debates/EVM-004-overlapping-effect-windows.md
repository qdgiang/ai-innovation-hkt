# EVM-004 — Resolve overlapping exception windows

> Priority: P0 · Status: `OPEN`

## Problem

Windowed exceptions may coexist with a standing decision, but rev 9 does not define two
contradictory exceptions on the same facet and overlapping dates.

## Options

- **Option A — Last write wins:** easy but silently hides an effective exception.
- **Option B — Hold the conflict pending (`PROPOSED`):** require window adjustment or explicit
  replacement before the second exception becomes effective.
- **Option C — Automatically split date ranges:** powerful but creates synthetic decisions and interval
  complexity that should be deferred.

## Acceptance criteria

- Conflicting effective exceptions for the same unit cannot overlap.
- Non-overlapping and compatible exceptions remain valid.
- Q&A returns one unambiguous effective value for an `as_of` time.
- An explicit replacement preserves the replaced exception in history.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — FIX; Option B adopted (rev-14 absorption queue).** Real edge G42 left open:
one-effective-per-unit never constrained *windowed* decisions against each other. Rule: at
effective-write time, a windowed decision whose `effect_window` overlaps an existing effective
exception on the same unit is **held `proposed`** with both windows shown — the proposer
adjusts dates or explicitly replaces (replacement supersedes the old exception through the
normal machinery, history intact). Non-overlapping exceptions coexist freely; `as_of`
resolution stays deterministic: standing decision, shadowed by at most one exception at any
instant. Interval-splitting (Option C) rejected — synthetic decisions would break
receipts-per-utterance. Consistent with settled #18: the hold waits for a human act, no clock.

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

# EVM-012 — Define deterministic late-event ordering

> Priority: P1 · Status: `OPEN`

## Problem

Transcripts, imports, delayed webhooks, and retries can arrive out of order. Arrival order can
rewrite present truth with older history, while equal timestamps make replay nondeterministic.

## Options

- **Option A — Arrival order:** operationally simple but historically incorrect.
- **Option B — Valid causality, then total event order (`PROPOSED`):** honor valid causal links, otherwise
  order by `event_ts → recorded_at → stable_event_id`; old events enter history without rewind.
- **Option C — Full bi-temporal model:** strongest query semantics but defer until current replay needs
  prove insufficient.

## Acceptance criteria

- Late older history does not change the current projection.
- Equal event timestamps replay deterministically.
- An explicit supersession with impossible chronology goes to triage.
- Views expose event and recorded timestamps when they differ.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — FIX-lite; Option B adopted (rev-14 absorption queue).** Rev 13 already has the
spine: fold by event `ts`, `recorded_at` stored, late-older history born `superseded` without
disturbing the present (G31), dual stamps in views. Adopted additions: (a) the deterministic
tiebreak chain `event_ts → recorded_at → stable_event_id` so equal timestamps replay
identically every time — cheap and essential for the replay demo's credibility; (b) an
explicit supersession whose chronology is impossible (claims to supersede something newer than
itself) goes to **triage**, never into the fold. Option C (full bi-temporal) stays exactly
where it already is: §Deferred, until real query needs prove the current model insufficient.

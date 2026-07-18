# EVM-013 — Prevent false signal-ledger merges

> Priority: P1 · Status: `OPEN`

## Problem

Free-text topic matching can merge unrelated risks across projects, tasks, or similarly named
external parties. A false merge can create or resolve the wrong blocker.

## Options

- **Option A — Global free-text topics:** minimal schema with high false-merge risk.
- **Option B — Scoped structured identity (`PROPOSED`):** key by project, task when known, party, and
  normalized topic; confirm the first party match and audit merge/split corrections.
- **Option C — Fully automatic embedding clusters:** useful discovery but too probabilistic to own domain
  identity without human correction.

## Acceptance criteria

- Same words in different projects do not merge by default.
- A first fuzzy party match requires confirmation.
- Merge/split keeps all source citations and correction events.
- Signal contradiction cannot resolve a human-asserted blocker; PIC/authority action is required.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — FIX-lite; Option B adopted (rev-14 absorption queue).** Adopted: signal identity
key = (project, task?, party?, normalized-topic) — project scoping is free under
one-group-one-project, so same words in different projects never merge by default; the first
fuzzy party match confirms on first use (already the rev-13 rule for `waiting_on`); ledger
merge/split corrections are append-only events reusing the supersession-pointer pattern, all
citations preserved. One clarification absorbed with it: signal *expiry-on-contradiction*
(rev 13's ledger rule) applies to **signals only** — a human-asserted `blocked` state is never
resolved by contradicting chatter; only a PIC/authority act clears it, which sharpens the
existing asserted-vs-derived distinction (G15). Option C embedding clusters rejected as an
identity owner — fine later as a *suggestion* source feeding the confirm lane.

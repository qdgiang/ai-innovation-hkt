# EVM-007 — Make Q&A truth-state and access aware

> Priority: P0 · Status: `OPEN`

## Problem

Q&A can mix effective decisions, pending proposals, exceptions, challenges, history, and inaccessible
evidence. Generating from all data and redacting later risks both false truth and leakage.

## Options

- **Option A — Retrieve everything, redact the final answer:** high recall with an unacceptable leakage
  boundary.
- **Option B — Permission-first, truth-aware retrieval (`PROPOSED`):** answer from effective state and
  label exceptions, pending/challenged alternatives, superseded history, and backlog.
- **Option C — Retrieve effective records only:** safe but loses valuable “why” and disagreement context.

## Acceptance criteria

- Access filters run before retrieval/prompt construction.
- Pending or challenged records are never phrased as current truth.
- Windowed decisions answer correctly for the requested time.
- Inaccessible evidence is not quoted; the answer states citation availability honestly.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — SPLIT: truth-states COVERED; access filtering ROADMAP.** The truth-state half of
Option B is rev 13's existing contract: answers derive from the fold of *effective* decisions;
exceptions render as windowed shadows, never schedule changes (G42 — hero Q&A beat #2);
proposals and challenges are never phrased as current truth (pending has no projection impact
by definition); superseded history is reachable but badged (show-inactive); extraction backlog
is disclosed on any read (backlog notice). The access half presumes read ACLs that the demo
deliberately does not have (settled #3/#4: one org, persona switcher, no login) — under demo
scope every citation is accessible, so "filter before retrieval" is vacuously satisfied.
Permission-first retrieval becomes a hard requirement the day D8-style ACLs land — tied to
EVM-001/EVM-020 on the roadmap, with this file's criteria as the gate.

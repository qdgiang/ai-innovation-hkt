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

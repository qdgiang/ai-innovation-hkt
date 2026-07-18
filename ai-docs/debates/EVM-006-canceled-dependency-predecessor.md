# EVM-006 — Define dependency behavior when a predecessor is canceled

> Priority: P0 · Status: `OPEN`

## Problem

Rev 9 unblocks dependents when predecessors complete but does not define cancellation. Cancellation
usually means the expected output will never arrive, not that the dependency was satisfied.

## Options

- **Option A — Any terminal state satisfies:** simple but can green-light work missing its prerequisite.
- **Option B — Only `done` satisfies (`PROPOSED`):** `canceled` marks the edge `needs_rewire`; a lead
  removes the edge when the output is no longer needed.
- **Option C — Configurable dependency policies:** expressive, but defer until concrete use cases require
  more than completion-required semantics.

## Acceptance criteria

- Canceling a predecessor never emits “unblocked.”
- Completing the last required predecessor may emit a confirm-resumption ping.
- Merge redirects dependency identity; it does not satisfy the dependency by itself.
- Multiple predecessors use AND semantics unless the model explicitly changes later.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — FIX; Option B adopted in full (rev-14 absorption queue).** Correct catch: rev 13
defines unblock-on-done and close-out edge-killing, but a mid-flight `canceled` predecessor was
undefined. Adopted semantics: only `done` satisfies an edge; canceling a predecessor flips its
outgoing edges to `needs-rewire` (the vocabulary G59 transfers already use) and flags the
dependent's PIC + lead — never an "unblocked" signal; `merged` redirects edge identity to the
survivor (G60) without satisfying anything; a lead removes an edge explicitly via the existing
`dependency remove` op when the output is genuinely no longer needed. AND semantics across
multiple predecessors confirmed as the standing rule. All four acceptance criteria adopted
as-is.

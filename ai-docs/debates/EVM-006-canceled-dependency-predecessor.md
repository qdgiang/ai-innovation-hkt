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

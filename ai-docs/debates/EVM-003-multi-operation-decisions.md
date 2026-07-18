# EVM-003 — Define atomicity for multi-operation decisions

> Priority: P0 · Status: `OPEN`

## Problem

One extracted sentence may contain operations with different targets, authority, or validity. A
single lifecycle status cannot honestly represent a partially effective decision.

## Options

- **Option A — Make every multi-op decision atomic:** simple, but one invalid or differently-authorized
  operation blocks unrelated valid work.
- **Option B — Normalize heterogeneous operations into a linked decision bundle (`PROPOSED`):** each
  child has one authority/transaction boundary; homogeneous all-or-nothing operations stay atomic.
- **Option C — Allow partial-effective decisions:** expressive but introduces per-op lifecycle and much
  more complex replay/UI.

## Acceptance criteria

- Atomic decisions validate every operation before committing any operation.
- Different authority domains produce linked children rather than partial effectiveness.
- The UI preserves the original human statement as bundle context.
- Retry or rejection cannot leave half of an atomic child applied.

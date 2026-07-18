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

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — MODIFIED; all-or-nothing per decision, no bundle entity for MVP.** Adopted:
every op in a decision validates before any op commits; a decision is never partially
effective (criteria 1 and 4). Not adopted for MVP: splitting heterogeneous-authority
utterances into linked child decisions — a mixed-authority sentence is rare in a 10-person
NPO, and the predictable degradation is cheap: the whole decision routes as ONE `proposed`
record to the *highest* required authority, who can approve it in one act or re-issue the
uncontested part themselves. One utterance = one decision = one status, and the original
statement stays intact as the citation (criterion 3 satisfied without a bundle). Linked
bundles move to roadmap, revisited if real usage shows mixed-authority utterances are common.

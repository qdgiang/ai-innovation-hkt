# EVM-015 — Define evidence retention, deletion, and redaction

> Priority: P0 · Status: `OPEN`

## Problem

EverMind caches source revisions as receipts, but delete signals, retention, consent, redaction,
and access to cached copies are not a complete policy. Confirmed truth and raw evidence have
different retention needs.

## Options

- **Option A — Retain raw evidence forever:** strongest audit with unacceptable privacy/storage risk.
- **Option B — Configurable retention plus tombstone/redaction (`PROPOSED`):** preserve audit metadata
  and derived decisions while governing raw text/file access separately.
- **Option C — Delete all derived records with source deletion:** privacy-simple but destroys institutional
  memory and decision accountability.

## Acceptance criteria

- Policy distinguishes raw source, revisions, confirmed records, and audit metadata.
- Delete/redaction events are auditable and authorization-checked.
- A surviving decision shows `source unavailable/redacted` rather than fabricating a receipt.
- Cached-copy access follows explicit scope and retention policy.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — SPLIT: citation states FIX-lite now; retention policy ROADMAP.** Rev 13 already
holds the mechanics: revisions append-only, deletes tombstone (record kept, text redactable
per consent posture), cached copies labeled when a source link dies, receipts never fabricated.
Adopted now (rev-14 queue): the explicit citation-state vocabulary — `live` ·
`edited-after-capture` (G45 badge) · `source-deleted` · `redacted` — rendered on every receipt,
so a surviving decision says plainly what its evidence's condition is. Redaction is an
authorized act (coordinator-level config op, logged). Deferred to roadmap: configurable
retention windows per class (raw source vs revisions vs confirmed records vs audit metadata)
and consent-policy tooling — org-governance work, not 48h work; the demo posture stays what
was settled long ago: bot presence = visible capture, published schema. Option C rejected
outright — source deletion never deletes derived institutional memory.

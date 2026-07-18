# SPEC D1–D8 — Settled corrections for EverMind rev 10

> Intended use: merge-request body or umbrella spec issue.
> Status: `SETTLED`; this file records approved direction, not implemented behavior.

## Why this MR is needed

`design-v2` rev 9, scenarios, `data-v2`, and the agreed product direction disagree at several
seams. Rev 10 should absorb the eight corrections below before schemas or connectors are rebuilt.

## Corrections

### D1 — Temporal group mapping

Use `group_bindings(group_id, project_id, valid_from, valid_until)` with a no-overlap invariant.
At any instant a group belongs to one project. Cutover archives rather than deletes the old
project. A message sent before cutover but delivered late uses the old binding; post-cutover
chatter defaults to the new project. See EVM-009 for operational cutover scenarios.

### D2 — Mutable decision snapshot, immutable history

`decisions` is the current snapshot; every mutation appends a `decision_event` or revision.
Correcting/refining the same intent is an amendment; choosing a materially different alternative
creates or identifies a superseding decision. A material amendment to an effective decision
revalidates authority and emits a correction notification to the group.

### D3 — Dashboard as a write surface

A dashboard edit runs `domain command → authorization → event → projection → outbox`. It never
updates task projections directly and never creates a fake human message for AI re-ingestion.
See EVM-001, EVM-010, and EVM-021 for authentication, delivery, and concurrency.

### D4 — Explicit project type

Use `project_type: campaign|program`; `end_date` is independent and optional. A campaign without
an end date stays valid but warned and cannot default dates until one exists. A program may have a
planning end date without campaign-style defaulting or automatic close.

### D5 — Platform-generic user identity

Map external identities to one internal user with a key scoped by connector/account/workspace,
platform, and platform user ID. An internal user may have several identities; an external identity
maps to at most one internal user. Never auto-merge by display name.

### D6 — Approval requirement and event ledger

Replace singular approval semantics with an `approval_requirement` plus multiple
`approval_events`. Each event records actor, action, method (`reply`, `reaction`, `dashboard`,
`marker`, `API`), authority basis, role/membership snapshot, timestamp, and citation. A reducer
makes the decision effective only when the requirement is satisfied. See EVM-019.

### D7 — Executable v2 acceptance tests

Create three layers: fixture integrity, deterministic domain scenarios, and extraction/evaluation
quality. Core domain acceptance tests must not require live Telegram or Discord. Prevent v2 tests
from silently reading the v1 `data/` fixtures. See EVM-008.

### D8 — Project-scoped visibility

Project members may read all project tasks, decisions, and signals, including lead-owned records;
roles constrain writes. Raw evidence remains source-scoped. Cross-project access is limited to a
dependency carve-out or explicit publication. See EVM-007 and EVM-020.

## MR acceptance checklist

- [ ] Rev 10 entity definitions express D1–D8 without relying on comments or fixture convention.
- [ ] S22 uses temporal bindings and archive semantics.
- [ ] Decision replay reconstructs every amended snapshot.
- [ ] Dashboard writes traverse the same domain authorization path as chat writes.
- [ ] Campaign/program behavior is keyed by `project_type`, not nullability alone.
- [ ] Identity uniqueness includes connector/workspace scope.
- [ ] Two-key and all-leads approvals are representable.
- [ ] Visibility is enforced before Q&A retrieval.
- [ ] `data-v2` has executable tests independent of live platform services.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13; per-correction verdicts)

This file predates revs 11–13 (settled #18 no-expiry, #19 run 9, #20 read-only bot). The
`SETTLED` label is corrected per item below — several of these collide with explicit standing
rulings, which win.

- **D1 — REJECTED.** Settled #13b is a deliberate user ruling: one group ↔ one project,
  *permanently*. New season = new group (S22). No `group_bindings` table. Full reasoning in
  EVM-009's resolution; platform-group reuse, if ever needed, is an adapter-level remap to a
  new logical group.
- **D2 — REJECTED as stated.** Settled #2 stands: decision bodies are immutable; the only
  post-write change is status. "Same intent refined" = the grace-window amend (markers) or a
  superseding decision — the supersession chain IS the preserved identity, one click away.
  The mutable row this correction wants already exists in the right place: the *projection*
  (tasks fold), never the decision. Correction notifications are feed entries (settled #20).
- **D3 — ADOPTED (already true).** Dashboard acts are domain commands through the same
  authorization path as chat — rev 13's dashboard lanes; the pipeline wording lands in the
  next design pass as `command → authorization → event → projection → feed` (outbox leg
  struck per settled #20). Fake-ingested messages were never a lane.
- **D4 — ADOPTED; FIX (rev-14 queue).** Explicit `projects.kind: campaign|program`;
  `end_date` becomes independent data. Campaign without a date = warned, no defaulting until
  dated; a program may carry a planning date without inheriting defaulting or auto-close.
  Good correction — nullability was doing double duty.
- **D5 — ADOPTED; FIX-lite (rev-14 queue).** Identity key = (platform, connector/workspace
  scope where the platform needs it, platform_user_id); one internal user ↔ many identities;
  never auto-merge by display name (G44 already keys on platform_user_id — this widens the
  key). Trivially satisfied by the single-bot demo.
- **D6 — PARTIAL.** The event-ledger direction is rev 13's act-evidence layer (reaction_acts,
  approval citations with `rev_at_act`, method vocabulary reply/reaction/dashboard/marker).
  A generalized `approval_requirement` + reducer is NOT adopted for MVP: `any`
  (rank-sufficient) plus two hard-coded multi-party cases (two-key transfer G59, all-leads
  project policy) cover every scenario in the register; the general table is §Deferred. See
  EVM-019's resolution.
- **D7 — ADOPTED.** The Phase-1 work order (EVM-008): three test layers, data-v2-only guard,
  platform-free core tests.
- **D8 — ROADMAP.** Read ACLs conflict with settled #3's demo scope (persona switcher, no
  login). Adopted as the production posture — project-scoped reads, source-scoped raw
  evidence, carve-outs and publication as the only cross-project paths — activating together
  with EVM-001 auth and EVM-020 publication.

**Checklist disposition:** temporal-bindings item VOID (D1 rejected); amended-snapshot replay
VOID as phrased (D2 rejected — replay reconstructs supersession chains, which it already
does); dashboard-path, project_type, identity-scope, two-key/all-leads representability, and
executable-tests items land with the rev-14 absorption + Phase 1; visibility-before-Q&A moves
to the D8 roadmap gate.

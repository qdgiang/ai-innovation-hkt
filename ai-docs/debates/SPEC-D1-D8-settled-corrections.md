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

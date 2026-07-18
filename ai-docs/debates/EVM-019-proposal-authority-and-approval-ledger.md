# EVM-019 — Proposal authority and approval ledger

> Priority: P0
>
> Status: `PREFERRED` — authority matrix and bounded autonomy are approved; lifecycle/schema
> details remain open.

## Problem

Members need to propose changes without silently changing shared truth. At the same time, making
every note or progress report wait for a lead creates approval spam and a new single point of
failure. The existing singular `approved_by_user_id`/`approval_via` shape also cannot represent
PIC consent plus lead approval, two-project transfer, or all-leads approval.

## Options considered

### Option A — Approval for every member-originated change

All task mutations wait for a lead. This is predictable and conservative, but notes, progress,
and completion claims fill the approval queue. A forgotten queue blocks routine execution.

### Option B — Bounded autonomy (`PREFERRED`)

Use a deterministic facet registry, not an AI materiality guess. PIC execution events apply
immediately; changes to shared/material facets become proposals routed to the required authority.
This preserves authority without making the lead a bottleneck for ordinary work.

### Option C — Per-task autonomy configuration

Each task chooses an approval policy. This is flexible but adds configuration, inconsistent team
behavior, and more edge cases. Defer until real usage shows that a global default plus explicit
exceptions is insufficient.

## Approved authority matrix

| Action | Result |
|---|---|
| PIC appends note or evidence | Apply immediately with actor and revision history. |
| PIC updates `todo → doing → done` | Apply immediately. Reopen creates a correction and retracts prior green lights. |
| PIC reports `blocked` or `resolved` | Apply immediately; radar and dependency projections recompute. |
| PIC changes description, dates, scope, priority, or budget | Proposal to the team lead. |
| PIC handoff | Incoming PIC accepts **and** lead/acting lead approves. |
| Member changes another member's task | Proposal to authority over that task. |
| Member changes team policy | Proposal to that team lead. |
| Team lead changes project-wide facet | Proposal to project owner/coordinator. |
| Actor changes a higher-authority decision | Proposal to an authority able to amend/supersede that decision. |
| Project owner/coordinator changes a project facet | Effective unless a separate multi-domain requirement applies. |

UI attribution must preserve both contributions: `Minh proposed · Mai approved`. Approval does
not erase authorship of the idea; authorship does not imply authority.

## Proposed approval-ledger shape

- `proposal`: target, facet, operation, current value/version, proposed value, proposer, status.
- `approval_requirement`: required authority domains and combination rule (`any`, `all`,
  `two_key`).
- `approval_event`: actor, action (`approve`, `reject`, `challenge`, `withdraw`), method, authority
  basis, role/membership snapshot, timestamp, and citation.
- `proposal_revision`: immutable record of material edits; prior approvals are invalidated when
  the approved content changes.
- The current proposal/decision row is a snapshot; events are the audit source and replay input.

## Core flow

1. Capture proposal and resolve target/facet/current version.
2. Show the proposer a receipt saying that the projection has not changed.
3. Resolve required authority and announce the pending proposal.
4. Collect approvals/consents as separate events.
5. Revalidate target version, authority, and terminal state at final approval.
6. Apply atomically, update projection, and notify the group with proposer and approver.

## Edge cases to retain in scenarios

- Incoming PIC accepts but the lead rejects the handoff.
- Lead approves but the incoming PIC has not accepted.
- Original decision was made by a coordinator; a team lead cannot supersede it.
- Proposal is amended after one of two required approvals.
- Target is canceled, merged, transferred, or concurrently changed before approval.
- PIC marks `done`, later reopens, and EverMind retracts dependent green lights.
- An optional future task rule requires completion review without changing the default PIC-done
  behavior.

## Acceptance scenarios

- A PIC note appears immediately and cannot change task facets.
- A sentence presented as a note but changing the deadline creates a deadline proposal.
- A member's date proposal leaves the task unchanged until team-lead approval.
- A PIC replacement applies only after incoming acceptance and authority approval.
- A project-wide proposal by a team lead routes to the coordinator.
- Every effective change can display proposer, approver(s), method, basis, and evidence.

## Open decisions for the GitHub issue

- Exact `approval_requirement` combinations needed for MVP.
- Whether any task may opt into `completion_requires_approval` in MVP or roadmap only.
- How acting leads/coordinators are configured and time-bounded.
- Whether a material amendment keeps the proposal ID or creates a linked successor after review
  has started.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — Option B confirmed (it is rev 13's model); matrix adopted with two changes; the
open decisions decided.** Bounded autonomy = the existing facet registry + update lanes: PIC
notes/evidence/progress/done apply immediately; material facets route as proposals to the
required authority; no AI materiality guess. Matrix deltas: (1) **PIC handoff two-key →
REJECTED for MVP** (see D10 in the SPEC file) — assignment stays a plain authority op;
incoming consent is social, and the overload warning is the pushback lane; two-key stays
special-cased where it already exists (cross-project transfer, G59). (2)
`completion_requires_approval` → **roadmap only**; default PIC-done stands. The MVP approval
ledger is the rev-13 act-evidence layer — `decisions` (snapshot) + `decision_citations`
(kind=approval, `rev_at_act`) + `reaction_acts` + `approved_by`/`approval_via` — which already
renders "Minh proposed · Mai approved". `approval_requirement` combinations for MVP: `any`
(rank-sufficient), plus the two hard-coded multi-party cases (two-key transfer, all-leads
project policy); a generalized requirement/reducer table is §Deferred (multi-step approval
chains). Amendment identity (open decision 4): settled #2 answers it — bodies are immutable;
within the grace window an edit amends, after it a proposer's new value is a **linked
successor** that withdraws the old (settled #17b), and prior approvals never carry across
content changes (G65 binds approval to the seen revision). Acting-authority configuration →
roadmap; MVP uses the coordinator apex + rootless fallback. Receipts/announcement steps in
the core flow read dashboard-side under settled #20.

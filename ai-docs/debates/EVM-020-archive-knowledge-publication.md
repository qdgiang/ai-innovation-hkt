# EVM-020 — Archive knowledge publication under project-scoped access

> Priority: P0
>
> Status: `PREFERRED` — preserve all options; Option B is the current preference.

## Problem

EverMind defaults to project-scoped access, but institutional memory must survive project closure
and volunteer rotation. Scenario S22 assumes a new project can ask why an old project chose a
venue or which sponsor worked previously. Making the full archive globally searchable would leak
raw discussions, files, budgets, contact notes, and personnel context.

Source conflict: [S22 — new season](../scenarios/S22-new-season.md) assumes archive reach-back,
while the approved D8 rule makes reads project-scoped by default.

## Invariants

- Project members read confirmed resources in their project.
- Raw chat/file evidence stays source-scoped unless explicitly published.
- Cross-project dependency views expose only their minimal carve-out.
- Publication must not rewrite, detach, or reattribute the original record.
- Q&A filters accessible sources before answer generation.
- Removing publication does not delete the source project's audit history.

## Visibility scopes under debate

| Scope | Meaning |
|---|---|
| `source` | Only users with access to the originating group or file. |
| `project` | Default for confirmed records; all project members may read them. |
| `org_published` | Reusable knowledge explicitly published for cross-project retrieval. |

## Options considered

### Option A — Automatically expose the full archive organization-wide

Maximum recall and simplest cross-season Q&A. It breaks the project-scoped default and can expose
sensitive raw context. It is not recommended as the default, but remains an explicit high-trust
organization policy to consider later.

### Option B — Curated publication bundle (`PREFERRED`)

At project close, EverMind proposes a reusable-knowledge bundle. The project owner reviews the
content and the coordinator approves organization-wide publication. New projects search the
published bundle; source evidence remains gated by its original permissions.

Candidate bundle content:

- Retrospective summary and outcomes.
- Reusable decisions with rationale and supersession context.
- Lessons learned and next-time policies.
- Approved vendor/institution knowledge with sensitive fields removed.
- Links to original records and citation-availability badges.

Exclude by default: raw chat, private files, credentials/access information, personnel issues,
unresolved allegations, and unrestricted contact notes.

### Option C — On-demand access request

A user asks about an old project and EverMind requests access from the archive owner. Privacy is
strong, but users cannot discover knowledge they do not know exists, and the former owner may be
unavailable. Keep as a fallback for non-published material rather than the primary memory model.

## Proposed Option B flow

1. Project enters `closing`; EverMind generates a draft publication bundle.
2. Project owner may include, exclude, redact, or amend bundle items.
3. Coordinator approves the cross-project visibility change.
4. Approved items gain `org_published` visibility while retaining source project and citations.
5. Q&A in a new project may answer from published items and says when raw evidence is inaccessible.
6. Amend, revoke, or supersede publication through new events; previously delivered answers keep
   their audit reference but future retrieval follows current visibility.

Program projects that do not automatically close need a manual “publish reusable knowledge” flow
using the same review and approval rules.

## Edge cases to retain in scenarios

- Project owner departed before close-out review.
- A new project needs knowledge before the old project closes.
- A published decision is later corrected, superseded, redacted, or loses its evidence.
- Vendor identity is reusable but project-specific price/contact notes are sensitive.
- Only selected projects, rather than the whole organization, should receive a bundle.
- Bundle contains mixed safe and sensitive items; approval must be item-level or support partial
  approval without publishing everything.
- Q&A finds relevant private archive content but only public metadata is accessible.

## Acceptance scenarios

- A new volunteer can retrieve a published venue rationale without joining the old project.
- The answer cites the published record and does not expose inaccessible raw chat.
- An unpublished personnel discussion never appears in cross-project Q&A.
- Revoking publication removes the item from future cross-project retrieval but preserves the old
  project's history.
- Coordinator approval alone cannot publish content the project owner explicitly excluded.

## Open decisions for the GitHub issue

- Whether publication requires project-owner review plus coordinator approval or coordinator
  override when the owner is unavailable.
- Publication granularity: individual record, topic collection, or whole bundle.
- Visibility targets: organization-wide only or selected projects/teams as well.
- Retention and revocation behavior for answers already generated from a publication.
- Which party fields are global identity versus project-scoped relationship knowledge.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — Option B adopted as the production direction; the MVP slice is the
retrospective.** The S22-vs-D8 "source conflict" dissolves once sequenced: the demo has no
read ACLs at all (settled #3 — one org, persona switcher), so S22's archive reach-back works
today with zero publication machinery, and nothing leaks that the whole org couldn't already
see. The **retrospective digest (G41) is the v0 publication bundle**: generated at close-out,
archived, quotable by Q&A — shipped / didn't ship / decisions with rationale and supersession
context / next-time policies / final counters, which is most of the candidate bundle list
already. The curated flow (owner reviews item-by-item, coordinator approves, `org_published`
visibility scope, revocation-without-history-loss, program projects' manual publish) activates
together with D8 ACLs on the roadmap — this file's invariants, edge cases, and acceptance
scenarios are pre-approved as that feature's spec. Option A remains a legitimate explicit
org-policy toggle (it is effectively what the demo runs); Option C stays the fallback for
never-published material.

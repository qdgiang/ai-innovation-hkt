# Design v2 — decision-driven tasks (rev 13)

> Consolidates: the human review (`UPDATE_REVIEW_FROM_HUMAN.md` + `decision-log.xlsx` /
> `task-log.xlsx`), the settled decisions of 2026-07-18, and **all fixes from scenario
> verification S1–S15** (`scenarios/README.md`, gaps G1–G40 — that register is this revision's
> change log). This file is the single source of truth; `ai/schemas.py` is stale until rebuilt
> from it. Supersedes the record model in `features.md` where they conflict.

## The pivot in one paragraph

Decisions are the write path, tasks are the projection. A task's row is the fold of the
`effective` decisions that touched it plus its PIC progress updates. Decisions are append-only —
a decision's body is immutable; the only post-write change is its `status` (a new effective
decision flips the one it replaces to `superseded`). "Blocker" is a task state with structured
wait info; weekly statuses are computed, not extracted. What survives from v1: `Message`,
citations as the trust anchor, ambient capture, markers as the deterministic lane,
precision >> recall.

## Settled decisions

| # | Decision |
|---|----------|
| 1 | Digest is **per-team**, posted to that team's chat group via the group mapping. |
| 2 | **`Decision` is first-class and append-only**; new decisions are born `effective` (or `proposed`, see lifecycle) and flip what they replace to `superseded` in the same write. PIC progress lives in a separate lightweight `task_updates` stream. Time-travel replays the ts-ordered union. |
| 3 | Hierarchy **modeled, not enforced**: org data + persona switcher; no login. Chat path is genuinely identity-checked (platform user ids). Real auth = roadmap. |
| 4 | Anti-surveillance constraint dropped: person-centric views/warnings in scope. |
| 5 | Weekly-status **extraction** killed; the digest is computed (and quotes lead wraps, §Digest). |
| 6 | Extraction is **batch + threshold-triggered** per live group: every N msgs (default 100) one AI pass over exactly that contiguous window, 1–N, N+1–2N, non-overlapping; each message AI-extracted exactly once. Bulk sources are the exception (§Windows). Markers stay per-message regex. |
| 7 | Demo org = **the synthetic corpus cast** (`data/answer_key.json` personas), seeded from a data file; no org-admin UI. |
| 8 | 2026-07-18: scenario rounds S1–S15 absorbed (G1–G40). Golden set relabels to production-shape windows. |
| 9 | 2026-07-18: iteration run 1 (S16–S17) absorbed — project lifecycle/close-out (G41), decision `effect_window` exceptions (G42), task merge (G43). |
| 10 | 2026-07-18: iteration run 2 (S18–S19) absorbed — provisional-user arrival lane (G44); plus proactive hardening: extraction windows are transactional/idempotent (§Windows), added while revising, to be verified by later runs. |
| 11 | 2026-07-18: probe run 5 (S24–S28) absorbed — message revisions + pinned citations (G45), media & forwards (G46), standing teams + org-level ongoing home (G47), team-less task governance (G48), proposal hygiene (G49). Clean-run counter reset; rev 5 awaits two fresh clean runs. |
| 12 | 2026-07-18: probe run 6 (S29–S33) absorbed — reply-target hydration + approval-by-reply (G50), org-level dependency matrix (G51), terminal-state locks + approval-time revalidation (G52), capture liveness & chat-id migration (G53), org timezone (G54), contested lamp + green-light retraction (G55). Counter still reset. |
| 13 | 2026-07-18 directives: **(a) the core models a generic chat platform** — send message, reply/thread, emoji react, edit, media, membership events; platform-specific quirks (id migrations, privacy modes, delete-signal availability) live in adapters, and scenario-testing stays platform-generic. **(b) One chat group ↔ exactly one project, permanently.** G47's standing-team/org-level machinery is recast as **program projects** (`projects.end_date` nullable): campaigns are dated, programs are not; each has its own groups. |
| 14 | 2026-07-18: run 7 (S34–S38; S38 clean) absorbed — idle/dateless lamp + anchored warnings (G56), project `end_date` as a decidable facet with defaulted-date cascade (G57), outbound-message registry + self-ingestion exclusion (G58), cross-project transfer op (G59). All MEDIUM-grade; counter still reset. |
| 15 | 2026-07-18 directive — **gap-acceptance policy**: small gaps MAY be accepted un-fixed when the fix's complexity outweighs the gap's likelihood/impact under the 48h hackathon clock. Every accepted gap is recorded in §Accepted gaps with rationale + workaround — accepted ≠ forgotten. Scenario verdicts triage: FIX (cheap or important) vs ACCEPT (niche + costly). |
| 16 | 2026-07-18: adversarial run 8 (S39–S43) triaged under #15 — FIXED: merge drops pair-internal edges + re-runs DAG check (G60), holdings-aware provisional pruning (G62), cross-boundary escalation routing (G63). ACCEPTED: peer-lead decision-churn detection (G61), in-negotiation proposal state (G64). Zero open unaccepted gaps at rev 9. |
| 17 | 2026-07-18 directives (proposal lifecycle): **(a) proposals expire** — 48h unapproved → `rejected(expired)`; the bot threads a notice onto the proposal's announcement ("expired, rejected — renew?"), and the proposer's 👍 flips it back to `proposed` with a fresh 48h. Replaces the open-ended 48h re-nudge. **(b) change-of-mind replaces** — a proposer's own different-value proposal on the same unit withdraws their older pending one; parallel pendings always mean *different* proposers. Rev 10. |
| 18 | 2026-07-18 **final directive — proposals never expire** (supersedes #17a; #17b stands): a `proposed` decision stays open until a **human act** resolves it — approval (→ effective) · explicit deny/veto/dismiss (→ rejected) · an authority's same-unit effective write (→ `rejected(overruled)` — an act, not a clock) · the proposer's own change-of-mind withdrawal. No TTL, no `approval_deadline`, no `rejected(expired)`, no renew loop; `PROPOSAL_TTL_HOURS` dropped. Anti-rot is **visibility, not clocks**: 48h approver nudge restored, pendings listed (aged) in every digest, approver bulk dismiss-stale kept. Rev 11. |
| 19 | 2026-07-18: adversarial run 9 (S44–S48) — the **contract-verb sweep** — triaged under #15. FIXED: approval acts bind to the seen revision (G65), corroboration lane + same-value guard (G66), reaction acts — storage, instant apply, withdrawal (G67), foreign-candidate linkage (the G68 fix half), group membership ≠ org + delivery reachability (G69). ACCEPTED: G68 residual (out-of-room decisions are never born effective). Zero open unaccepted gaps at rev 12. |
| 20 | 2026-07-18 final directive — **the bot never posts to groups** (read-only capture). Supersedes the chat-delivery half of #1 and every announcement/ping/reply lane: all output — proposal queues, nudges, radar, digests, retractions, sweeps, arrival confirms — surfaces on the **dashboard** (per-persona feed + approver inbox + team digest views); humans relay to chat when they want (a lead pastes a digest; the bot never speaks). Consequences: outbound registry dropped — no outbound ⇒ self-ingestion structurally impossible (G58 retired); chat approval acts target the proposal's **source message** (reply/react) — the bot-announcement target is gone; G69 reachability narrows to membership truth + an out-of-the-room flag. Rev 13. |

## Entities

Relationships: Project 1—\* Task · Task \*—\* Decision (task-scoped) · Decision \*—1 User
(`decided_by`) · Decision 0..1—0..1 Decision (supersedes/superseded_by) · Task \*—\* Task
(dependencies) · User \*—\* Team (`user_teams`) · Blocked-state \*—0..1 Party.

```
projects        {id, name, end_date?, status: active|closing|closed}
                  -- end_date null = ongoing PROGRAM project (weekend classes);
                  -- dated = CAMPAIGN project (the fair)
teams           {id, project_id, name}
chat_groups     {id, platform, platform_chat_id, project_id, team_id?}
                  -- exactly ONE project per group, permanently (settled #13); never remapped.
                  -- team_id null = project-wide group (all-hands)
users           {id, name, handle, role_rank,            -- 3=coordinator 2=lead 1=member (seed map)
                 manager_id?, platform_user_id?,        -- per chat platform; future auth bridge
                 status: provisional|active|departing|departed, departed_at?}
user_teams      {user_id, team_id, role_in_team}         -- matrix membership (khoa/thao/minh)
parties         {id, name, aliases[], kind: person|vendor|institution, contact_note?}
                  -- externals: chi Yen, InTheXanh, ward office…

tasks           {id, project_id, kind: project|ongoing, type: urgent|normal|undefined,
                  -- kind=ongoing: recurring/program work, exempt from end-date defaulting
                 description, status: todo|doing|done|blocked|canceled|merged, merged_into?,
                 start_date?, end_date?, end_date_defaulted,
                 blocked_waiting_on_party_id?, blocked_waiting_on_text?, blocked_since?, note?}
                  -- PROJECTION: fold of effective decisions + updates; never hand-edited.
task_assignments / task_teams                            -- DERIVED joins (projections, like tasks)

decisions       {id, ts, recorded_at, decided_by_user_id, decided_by_role_at_time,
                 scope: task|team|project,               -- G26: policies are first-class
                 description, context?, note?,
                 ops: [{target, facet, op, value}],      -- see Facet registry
                 effect_window?: {from, until},          -- G42: one-off exception, shadows within window
                 status: proposed|effective|superseded|rejected,
                 rejected_reason?: veto|overruled|withdrawn|dismissed,  -- settled #17/#18
                 supersedes_decision_id?, superseded_by_decision_id?,
                 approved_by_user_id?, approval_via: authority|delegation|self_confirm?,
                 created_from: marker|llm|dashboard|transcript, confidence}
decision_tasks  {decision_id, task_id}                   -- task-scoped decisions (may be several)
decision_citations {decision_id, message_id, kind, rev_at_capture, rev_at_act?}
                                                          -- kind: evidence|approval|corroboration
                                                          -- (G65/G66); chat-originated ⇒ ≥1
                                                          -- evidence citation, enforced;
                                                          -- pinned to the revision cited; approval rows
                                                          -- also pin rev_at_act, the revision the
                                                          -- approver actually saw (G65)

task_updates    {id, ts, recorded_at, task_id, actor_user_id, kind: status|note,
                 payload, created_from: marker|llm|dashboard, confidence?, source_message_id?}
signals         {id, kind: blocker|dependency|ask|parked, task_id?|topic, excerpt,
                 message_id, ts, window_id, status: open|promoted|expired}   -- the weak-signal ledger
task_dependencies {predecessor_task_id, successor_task_id, created_by_decision_id,
                 status: requested|confirmed}
messages        {id, source, channel, team?, author, ts, text, thread_ref?, raw_ref,
                 kind: text|photo|video|file|voice|sticker|system,
                 media_ref?, forward_origin?, current_rev}
message_revisions {message_id, rev, text, edited_at}     -- G45: edits append, never overwrite
reaction_acts   {id, message_id, user_id, emoji, ts, removed_at?}
                                                          -- G67: acts, not messages; adapter-fed,
                                                          -- TRACKED messages only (§Reactions)
group_members   {group_id, user_id, joined_at, left_at?}  -- G69: from membership events; room ≠ org
```

## Chat platform contract (generic — settled #13)

The core assumes a plain chat platform and nothing more: **send message · reply/thread
(`thread_ref`) · emoji reactions (add & remove) · message edits · media with captions · membership events**
(member joined/left; bot added/removed/permissions changed). Adapters normalize their platform
to this contract; anything platform-specific — id-migration events, privacy modes, whether
deletes are signaled, login widgets — is an adapter concern documented in that adapter's
runbook, never a core rule. Scenario verification targets this contract, not any one platform.

## Messages: mutability, media, forwards (G45–G46)

- **Edits:** `edited_message` updates append a `message_revision`; nothing is overwritten.
  Citations pin `rev_at_capture`; when `current_rev` moves past it, the citing record shows an
  **"evidence edited after capture"** badge (diff link) and the maker gets one nudge: "still
  stands? 👍 / reissue". **Markers are idempotent by source message:** an edit within a ~10-min
  grace window *amends* the marker-created record (typo lane); later edits never mutate records
  — badge + nudge only.
- **Deletes:** platforms may or may not signal them. When the adapter surfaces a delete →
  tombstone the message (record kept, text optionally redacted per consent policy). When it
  doesn't → undetectable, documented honestly; cached revisions are retained under the consent
  posture (bot presence = visible capture, published schema), and the popup labels text
  "cached copy" when a source link is discovered dead.
- **Media:** `kind` + `media_ref` (platform media ref / mime / name); `text` holds the caption
  (may be empty).
  Media lines enter windows as `[kind] caption`; caption-less media is context, not extractable
  content. Citations render kind-aware (📷/🎤/📎, fetch-on-click). Voice transcription = roadmap
  (store the file now; records may cite the voice message itself).
- **Forwards** route through the **relay lane**: `forward_origin` is the claimed source. Member
  origin → tagged for self-confirm; external origin → linked to a `party`, and an authorized
  member's confirm makes it effective.

## Reactions as acts (G67)

Reactions are **acts, not messages**: the adapter records them (`reaction_acts`) **only on
tracked messages** — the source messages of pending records and nudge targets (under settled
#20 there are no bot posts; sources are the only tracked class). Reactions on anything else are
dropped at the adapter: ack ≠ approval, resolved
structurally — a 👍 on ordinary chatter can never decide anything. Reaction acts apply
**instantly** to their known records (like dashboard taps — no window, no LLM). Receipts render
from the act row (who, emoji, when, on what) — the act row is the evidence. **Removal:** within the ~10-min grace window (the marker-edit constant,
reused) → auto-revert the effected record to `proposed` + an "approval withdrawn" retraction
entry (per the symmetry rule); after grace → the removal files a
**challenge** and the record wears an "approval evidence withdrawn" badge until resolved. Never
silent. (Replay corpora carry no reactions — live lane; the demo equivalence is the dashboard
tap.)

## Facet registry (what a decision can set, and what conflicts with what)

The supersession unit is **(scope-target, facet-key)**. At most ONE effective decision per unit
— enforced at effective-write time; effective-writes **serialize per target** (one transaction).

| Facet | Ops | Supersession unit / rule |
|---|---|---|
| `description` `status` `start_date` `end_date` `type` `kind` | set | per (task, facet). `status` via decisions only for cancel/revive; normal transitions are `task_updates` and never supersede anything |
| `assignment` | **add / remove / set** | per person-slot: `add` never supersedes; `set` supersedes all prior assignment ops; `remove` supersedes that person's `add`. Bare "giao X" in chat = **add** |
| `team` | add / remove / set | same slot rules |
| `dependency` | add / remove | per edge; `remove` supersedes the `add` |
| `attr:<name>` | set | per (target, attr-name): `attr:budget`, `attr:venue`, `attr:quantity`… extractor names the attr; candidates include the target's existing effective attrs so names converge |
| `note` | append | never supersedes, never conflicts |
| team/project scope | set on `attr:<topic>` | policies: `attr:donation-method`, `attr:entry-fee`, `attr:budget-cap`, `attr:class-schedule`… same one-effective rule per (scope, topic) |
| `merge` | task-scoped, on the survivor | absorbed task → `status: merged, merged_into: survivor`; updates/signals/citations/dependencies re-point (deps deduped), assignments union; the absorbed task's effective decisions enter the survivor's per-unit resolution (newest wins, rest flip superseded — normal machinery reused). Authority: lead over any owning team of either task. **Edges between the merged pair are dropped** (identity confusion, not sequencing), and the DAG check re-runs over the survivor's edges — a cycle aborts the merge with the path shown (G60). Split = compose (create children + refine parent), not a new op |
| `project` (task) | set | **cross-project transfer (G59)**. Authority: two-key — source lead + destination lead (either proposes, the other's approval effects it; coordinator alone suffices). Transaction: re-validate all edges vs the G51 matrix (violations → `needs-rewire`, PICs notified); clear `task_teams` (destination re-teams, else project-level per G48); re-evaluate dating under the destination; pending proposals on the task → `pending-revalidation`, re-routed to the new home's authority. History keeps its old-project context |
| `end_date` (project scope) | set | **campaign reschedule (G57)**. Authority: coordinator (or all-leads approval). Cascade in-transaction: unconfirmed `end_date_defaulted` tasks re-default to the new `end − 1` (staying flagged); confirmed/explicit dates untouched; violating or now-oddly-early dates surface as a one-time per-team "reschedule review" checklist (close-out machinery reused). Date-triggered `closing` re-arms/disarms on change; explicit coordinator closing sticks |

**Exceptions (G42):** a decision with `effect_window` does NOT supersede and is not blocked by
one-effective-per-unit: it **shadows** the standing same-unit decision inside its window and
auto-expires after (fold applies windowed decisions over standing ones only within the window).
Extractor rule: exception language ("CN này", "riêng buổi 20/7", "tuần này thôi") → windowed
decision, never a supersession suggestion. Popup renders "⏸ exception (dates)" under the
standing decision.

Peer conflict: if a second same-unit effective write arrives and the writers' ranks are
incomparable (§Hierarchy), the later decision is **held `proposed`** and both sides' leads (or
the fallback set) are tagged — explicit human tiebreak, never silent last-write-wins. The hold
persists until a lead acts (#18); the standing decision stays effective throughout — an
unresolved tie displaces nothing.

## Decision lifecycle

```
                          confidence ≥ τ AND author authorized/delegated
  (marker/dashboard: always) ───────────────────────────────► effective ──► superseded
  (new) ──► proposed ── approve / self-confirm 👍 ──► effective     │
              │  ▲                                                  └─ reject ─► rejected
              │  └ stays open: nudge approver at 48h; listed (aged)     (see Rejection)
              │    in digest — no clock ever changes a status (#18)
              └ reject / overruled-by-effective / withdrawn(own newer) ─► rejected
```

- **Born effective** requires ALL of: maker resolves to a cited author (or mapped speaker);
  maker authorized for the unit (§Authority) — or **delegated**: an authorized user's cited
  message in-thread explicitly authorizes them ("minh chốt luôn nhé") → `approval_via=delegation`,
  both messages cited; and `confidence ≥ τ` (config, start 0.8) for `created_from=llm`.
  Markers and dashboard writes are human-asserted: confidence 1.0.
- **Below τ, or relayed** (claimed maker not among cited authors — "posting for mai"): born
  `proposed`, tagged to the claimed maker; their 👍 = `self_confirm`. Anyone with rank ≥ the
  required authority may also approve. Never silently rejected.
- **Approval acts (equivalent):** dashboard tap · 👍 reaction (§Reactions — tracked messages
  only, instant) · **affirmation reply** ("ok
  chốt", "duyệt") by a sufficiently-ranked user to the proposal's source
  message (G50; there are no bot posts to reply to — settled #20) — the reply is cited as
  approval evidence; negation replies ("thôi",
  "khỏi") map to reject. Deterministic phrase list first, LLM only for ambiguity.
  **Approval binding (G65):** every approval act binds to the target revision current at the
  act's `ts` — approval citations carry `rev_at_act`. If capture finds `rev_at_capture ≠
  rev_at_act` (the target was edited between the approval and extraction), the decision is born
  `proposed` with the diff shown to the approver (G52's card); one tap re-confirms,
  re-citing the approval at the new revision. Any text change re-asks, even typo fixes — a
  spurious 👍 costs one tap; resolving "did the ops really change" costs a second extraction.
- **Open until resolved (settled #18):** a `proposed` decision has NO expiry — it stays open
  until a human act resolves it: approval · explicit deny ("thôi", veto, dashboard dismiss) ·
  a same-unit effective write by authority (swept `rejected(overruled)` — an act, not a clock) ·
  the proposer's own withdrawal (#17b). The clock never changes a status. Staleness is fought
  with visibility instead: one approver nudge at 48h, pendings listed (aged) in every digest,
  and the approver's bulk dismiss-stale (an explicit act, `rejected(dismissed)`). Uniform across
  hold reasons — below-τ, relay self-confirm, rank-gate and peer-conflict holds all wait the
  same way. Late approval of an old proposal is safe by construction: G52 revalidation re-checks
  the target's *current* state before anything takes effect.
- **Supersession** needs the **rank gate**: `rank(actor) ≥ rank(D_old.decided_by_role_at_time)`
  (snapshot). Fails → born `proposed`, tagged to the original maker / nearest sufficient rank.
- **Effective-write transaction:** insert new; flip the same-unit predecessor to `superseded`
  (+ back-pointer); **sweep** same-unit `proposed` decisions → `rejected` with
  `superseded_by := winner` (renders as "overruled by", authors notified).
  **Same-value guard (G66):** a candidate whose ops equal the current same-unit effective ops
  (op + value) converts to a **corroborating citation** on the standing decision — never a new
  decision or proposal. Attribution and `ts` never move on a restatement; the popup renders
  "✓ nhắc lại trong chat (ai, khi nào)" and Q&A answers may cite corroborating messages
  alongside the deciding source.
- **Rejection** (veto/`/forget`): allowed to the maker or anyone with rank ≥ maker; others file a
  **challenge** the maker resolves with one tap. Rejecting a decision **resurrects** each
  decision it superseded (restore `effective` iff no other effective same-unit superseder), then
  refolds. If the rejected decision had surfaced anywhere, a **retraction entry** hits the
  affected feeds; the next digest leads with corrections. Every rejection stores its `rejected_reason`
  (`veto|overruled|withdrawn|dismissed`).

**Terminal states & stale acts (G52):** `canceled` and `merged` tasks lock the lanes — the
update lane accepts notes only (a PIC's `!progress` on a canceled task gets a bot reply naming
the canceling decision; reopen = a lead `revive` decision), and ops aimed at a `merged` husk
auto-redirect to the survivor. **Approval-time revalidation:** approving any pending proposal
re-checks its targets *now* — target canceled → blocked with context (approve-as-revive or
dismiss); target merged → one-tap redirect to the survivor; same-unit value changed since
proposing → diff shown before confirm. Proposal cards always render current target state.

## Windows & extraction

- **Live groups:** per-group high-water mark; at +`EXTRACTION_BATCH_SIZE` msgs (default 100) one
  LLM call over exactly that window. Non-overlapping; each message extracted once.
- **Bulk sources** (transcript uploads, imports): the upload IS the window(s) — **flush on
  completion**, split at N if longer. (88-turn meetings must not wait for message #100.)
- **Flush-before-read:** digest generation and radar sweeps force-extract all partial windows
  first. Replay end flushes everything.
- **Context tail (cite-only):** each call also receives the last ~20 messages of the previous
  window marked "already processed — do NOT extract from these; you MAY cite them". Exactly-once
  extraction preserved; receipts can span the boundary (venue-thread case).
- **Reply-target hydration (G50):** for each window message whose `thread_ref` targets a
  message outside the window, the target (and its direct parent, ≤2 hops) is injected as
  `[replied-to, <date>] author: …` — context-only, never re-extracted, but **citable**. A terse
  "ok chốt" reply extracts into a decision citing both the reply (the authority act) and its
  target (the content).
- **No outbound lane (settled #20; retires G58):** the bot posts nothing to groups — capture is
  read-only, so there is no outbound registry and self-ingestion is structurally impossible.
  Acts on records ride the **source messages** (approval replies/reacts, hydration) and the
  dashboard. Platform system messages (joins/leaves) remain excluded from window transcripts,
  threshold counters, and evidence citability. (Human quotes of dashboard text are ordinary
  messages, handled by the normal lanes and dedup.)
- **Candidates:** the **project's** open tasks (group's team first) + the target scopes' existing
  effective policies/attrs + **open signals** for those topics + a **slim foreign index** (G68):
  id + title of other active projects' open tasks, listed last. This is the cross-window memory.
- **Extractor output per window:** proposed decisions (with scope, ops, supersedes-suspicion as a
  *suggestion* unless explicitly stated) · proposed `task_updates` (progress/notes) · `signals[]`
  (blocker-ish, dependency-ish, ask, parked — cheap to emit, no projection impact) ·
  `corroborations[]` (content value-matching a candidate effective decision → citation append on
  the standing decision, G66 — never a new decision).
- **Linkage returns** `task_id | task_id@foreign-project | NEW_TASK | TEAM_POLICY |
  PROJECT_POLICY | UNLINKED(triage)`. **Foreign-linked content (G68) is never born effective**,
  any rank: born `proposed`, routed to the target project's authority (their inbox; listed in
  that team's digest section, G63 carve-out rules) — effective only by the owning side's act.
  Triage cards offer foreign tasks as one-tap re-home targets.
- **Bare markers** (no `T-…` ref): the record is created instantly and deterministically; only
  its *attachment* runs through the linker (thread context counts as evidence). Marker grammar
  adds optional refs: `!decision T-12 …`, `!blocked T-12 …`, `!progress T-12 done`, `!depends T-12`.
- **Transcripts:** per-upload speaker map (display name → handle), auto-seeded from `users.name`
  + attendee header, confirmable at upload; unmapped speaker → decisions born `proposed`.
- **Ordering:** fold and supersession direction use event `ts`, not arrival. `recorded_at` stores
  ingestion time. A late-arriving decision older than the current same-unit effective one is born
  **already-superseded** (linked), entering history without disturbing the present. Views show
  both stamps when they differ. (Full bi-temporal querying = roadmap.)
- **Resilience (proactive, rev 4):** a window run is transactional — the high-water mark
  advances **only when the window's outputs are persisted**; on LLM failure after
  retry-with-backoff (429/503) the mark stays and the window re-runs on the next trigger or
  flush. Window runs are idempotent: outputs carry `window_id`, and re-running a window upserts
  by (window_id, dedup-key) instead of duplicating. A stuck window never blocks other groups
  (per-group marks are independent); markers are unaffected (no LLM in that lane). If windows
  are still failing when flush-before-read runs, the digest/radar proceed on available data and
  carry an explicit **backlog notice** ("extraction backlog: N windows pending — items may
  lag"); lagging data is never silently presented as current. Bare-marker records whose
  *attachment* can't run (linker down) exist immediately and sit in triage until it recovers.
- **Capture liveness (G53, platform-generic):** the adapter surfaces bot-membership events
  (removed / permissions lost) → immediate coordinator feed alert + dashboard health banner
  ("capture from <group> stopped — re-add the bot"); a daily membership self-check per mapped group backstops platforms whose
  events can be missed. While any mapped group is dark, the digest carries a capture-health
  line ("⚠ no capture from aiv-comms since 07-28") — a severed feed is never presented as a
  quiet week. (Platform oddities like chat-id migration are the adapter's job to absorb.)

### Update lanes (who may say a task moved)

| Author of the cited message | Effect |
|---|---|
| a PIC of the linked task | `task_update` auto-applies (status/note) — the review's carve-out |
| authority over the task | applies as decision-grade status change |
| anyone else | a PIC gets a confirm card (inbox); their tap — or 👍 on the cited message — applies it, attributed to the confirming PIC |

PIC statements **consistent** with the standing effective decisions of their own task are
captured as `note` updates, not proposals (execution zone). Only contradiction or scope change
escalates to a `proposed` decision. Lead wrap-shaped messages → team-scoped note (quoted by the
digest).

### Signals (the ledger)

One mention never promotes. Promotion: ≥2 corroborating signals, or 1 signal + staleness →
proposed `status=blocked` (with `waiting_on`/`since` from the ledger) or `requested` dependency
edge — **citations = all accumulated mentions**. Signals expire when contradicted or after N
quiet days; `parked` (explicit "để sau" only) and unanswered `ask` signals surface in the digest
after N days. Only `confirmed` dependency edges derive lamps; `requested` edges expire into the
digest's needs-attention list.

## Hierarchy & authority

- `rank` from the seed's `role_rank` map (coordinator 3 · lead 2 · member 1);
  `user_teams` gives per-team membership; `manager_id` gives the chain. Demo seed: **linh =
  coordinator** (root; corpus-faithful — she chairs the all-hands and holds budget sign-off),
  mai/phuong (and linh's events-lead hat) under her.
- `can_decide(actor, unit)`: task-scoped — actor in the manager chain above ANY owning team of
  the task (via `user_teams`); `NEW_TASK` — checked against the **chat group's team** (or any
  team the actor leads, for project-wide groups); team policy — that team's lead+; project
  policy — coordinator (or all leads jointly via approval). **Team-less tasks (G48):**
  project-level — any lead of that project decides (coordinator = supersession apex).
  `can_decide` is total: every unit has a defined authority set.
- **Rootless fallback** (general rule, always on): LCA undefined → escalate to all leads of the
  involved teams in the project-wide group; ranks incomparable → peer-conflict hold (§Facets).
- PICs edit their own tasks only (progress lane); anyone can propose anything.

## Blocked, dependencies, radar

- Blocked state carries `waiting_on` (party FK when matchable — alias fuzzy-match, confirm on
  first use — else text), `since`, and the owner; radar ages off `since`; digest groups open
  blockers **by party** ("3 teams waiting on chi Yen").
- Stored `blocked` (asserted) vs dependency lamp (computed) render distinctly; when the last
  blocking predecessor completes, the unblocked feed entry asks the PIC to confirm resumption.
- Edges: blocks-only, DAG (cycle check at write), created/removed by decisions, cross-team =
  visibility carve-out (minimal projection of upstream) + upstream-lead confirm (hackathon:
  auto-confirm) + escalation. **Admission matrix (G51):** same project ✓ · campaign ↔
  program ✓ (both directions — programs are shared infrastructure; these edges route
  escalation through the coordinator) · program ↔ program ✓ · campaign ↔ *different* campaign
  ✗ (incl. closed ones — knowledge reuse goes via Q&A/archive, not edges). Close-out kills
  edges with their campaign endpoint; program endpoints are never dragged.
- **Daily radar job** (scheduler): flush-before-read, then sweep lamps (`blocked`, `at-risk` =
  slack below threshold, `overdue`, `stale` = in-doing no event N days, `late-start`,
  `contested`, `idle`) → dashboard feed entries (settled #20). Cadence: PICs day 1 →
  +LCA/fallback day 3 → every 3 days; max one entry per task per day; `urgent` immediate.
  Team-less/project-wide tasks surface in the project-wide digest section (fallback: the
  coordinator's feed).
  **Reachability (G69, narrowed by #20):** with dashboard-only delivery nothing is ever tagged
  in-group, so reachability is informational: `group_members` keeps room membership true, and a
  PIC absent from their task's home group raises a once-per-cycle flag to the team lead
  ("re-add / reassign / offboard?") — they're out of the room where the humans talk.
- **Contested lamp (G55):** ≥K status flips (default 3) by ≥2 distinct actors within T days
  (default 7) → flag the task's lead once (feed), suggesting the compose-split ("production /
  sales-post?") with one-tap child-task proposals.
- **Green-light retraction (G55):** when a task leaves `done`, dependents whose feeds got an
  "unblocked" entry get the inverse entry ("on hold again — reopened"). Symmetry rule: anything
  the system asserted, it maintains or withdraws — decisions (retraction entries), backlogs
  (notices), lamps and derived entries alike.
- **Idle lamp (G56):** status `todo` and no event of any kind for N days (default 14),
  regardless of dates — catches dateless/unowned work no other lamp can see (programs have no
  countdown). Nudges the PICs, or the team lead when PIC-less (the common zombie case).
- **Cross-boundary escalation routing (G63):** an escalation about a campaign↔program edge
  raises **one card per endpoint side** (feed + that team's digest section), each rendering its
  own task plus only the carve-out projection of the other side, addressed to that side's PIC;
  the coordinator sees both. No extra visibility either side (settled #20: no group posts).

## Overload

Per-day concurrent load, next 14 days, from task windows across ALL the person's teams; weight
urgent×2, due-≤7d extra. Warn-don't-block: dashboard pre-assignment check; for chat-made assignments the check is
**post-hoc** — an overload flag lands on the decision and in the assigner's + assignee's feeds;
no veto in X hours = acceptance, noted on the decision. Structural bottleneck: task blocking ≥K downstream flagged task-centrically.

## Notifications (dashboard feed — settled #20)

The bot never posts to groups: every notification is a **dashboard feed entry** (per persona,
via the switcher) plus an **inbox item** when an act awaits someone. Per **decision**, not per
task: one entry listing affected tasks. Material changes only (effective decisions;
status/date/PIC/dependency updates — not note-only). Recipients: maker, PICs, PICs of
dependents, approver for proposals. **Proposals always land in the approver's inbox and the
team's pending queue** so pending ≠ invisible — in-chat visibility is deliberately zero; humans
relay when needed (a lead may paste a digest into the group; the bot never speaks). Entries
batch (~30 min) and dedup per person. Retractions append to the original entry and lead the
next digest's corrections.

**Proposal hygiene (G49; amended by settled #17):** a new proposal matching a pending one on
(unit, op, value) merges into it — citations union, proposers listed, one queue entry, one
nudge clock. Same-unit *different*-value pendings stay separate **only across different
proposers** (real alternatives). **Change-of-mind:** a proposer's own different-value proposal
on a unit **withdraws** their older pending one — old → `rejected(withdrawn)` with
`superseded_by := the newer` (popup: "replaced by the proposer's newer proposal"; the old
feed entry gains "↩️ replaced"); the new proposal runs a fresh clock. If the
older entry had merged several proposers, only this proposer is peeled off — the entry lives on
for the rest as a genuine alternative; the last proposer leaving withdraws it. (Edits inside
the ~10-min grace stay on the G45 amend lane; a new message routes here.) Approvers get bulk actions
(approve all / dismiss all from `<person>` / dismiss stale; dismissals = `rejected` with reason,
visible under show-inactive). Acts that didn't take effect stay visible to their actor on the
dashboard (settled #20 — no chat-side replies): marker-proposal filed (pending with @approver),
failed approval attempt (insufficient rank, shown on the card), repeat paste (collapsed into
the existing entry).
No hard rate caps — enthusiasm is a feature; persistent noise is a lead-side note, not a block.

## Project lifecycle (G41)

`active` → (`end_date` passes, or coordinator decision) → `closing` → (all open tasks resolved,
or coordinator decision) → `closed`.

- On `closing`: the radar STOPS overdue-pinging project tasks and instead raises one **close-out
  sweep** checklist per team (dashboard + digest, settled #20) — every open task proposed as `done` / `canceled (obsolete)` / `migrate to
  ongoing` (each resolution a normal decision; migrated tasks **transfer to a program project**
  of the lead's choosing — e.g. Weekend Classes — gaining `kind=ongoing` and exiting
  defaulting). Program projects and their tasks are untouched by a campaign's close (G47). A
  program project never auto-closes (`end_date` null): only an explicit coordinator decision
  closes it.
- On `closed`: a generated **retrospective digest** (shipped / didn't ship / decisions incl.
  next-time policies / final counters) is generated and archived (dashboard; a lead may share
  it to chat by hand); the project leaves active views.
  Late-arriving sources (e.g. the retro transcript) still ingest — they append to the archive
  via the normal late-arrival rules.
- **End-date defaulting (base rule, from the review):** a campaign task created without an
  `end_date` auto-sets `project.end_date − 1 day` + `end_date_defaulted=true`; the flag clears
  only by a human-confirming decision. `task.end_date > project.end_date` → warning. Program
  tasks and `kind=ongoing` are exempt. Warnings never block writes.
- **Where the warnings live (G56):** unconfirmed defaults and dateless campaign tasks appear in
  the digest's needs-attention line and get one radar nudge to the task's lead per the normal
  cadence — never per-day nagging. On a project `end_date` change, the G57 cascade re-defaults
  unconfirmed dates and posts the reschedule-review checklist.
- Defaulting amendment: in `closing|closed`, new tasks default to **no end date + warning**
  (never a past date).

## Users lifecycle

**Arrival (G44):** first message from an unknown `platform_user_id` in a mapped group
auto-creates a **provisional user** (rank 1, member of that group's team, name from the
platform profile). Provisional members get the full member experience — PIC-able, progress
lane, proposals, tags, load — and the team's lead gets a one-tap confirm card: "👋 <name>
joined — confirm membership?" → `active` (logged org event); silence → stays provisional, flagged in
the digest's team section, never silently dropped. Quiet provisional users are pruned after N days **only if
they hold nothing** (no PIC-ships, no pending proposals); with holdings, they are kept and
flagged to the team lead with a mini-sweep — one reassignment proposal per held task,
dismiss-or-adopt for pending proposals (G62). Historical actor references are never deleted. Org config changes (users, memberships, new-season teams)
are logged config operations, not decisions.

**Group ≠ org (G69):** `group_members` tracks room membership from membership events. A
member-left event NEVER changes `users.status` — org departure is only ever explicit (config op
/ coordinator decision), and only that triggers the offboarding sweep. Leaving a room just means they no
longer see that room's human chatter: the team lead gets the one-time flag (§Radar). Rejoins
reuse the known `platform_user_id` — never a spurious provisional.

`departing` triggers the **offboarding sweep**: proposed reassignments for their open tasks,
re-routing of pending approvals, list of parties only they chase, accesses named in their
blockers — the checklist surfaces on each affected team's dashboard section (and digest). `departed` leaves fan-outs and load; the
persona switcher hides them; history (snapshots) untouched. Onboarding brief (`/onboard <team>`)
is the mirror read: active tasks, effective decisions incl. team/project policies, open blockers
with parties, the buddy policy applied.

## Digest (per-team, computed — with the human wrap carried)

Skeleton from data: decisions (task + policy) with receipts · completed/created tasks · blockers
(grouped by party, aged) · at-risk/overdue lamps · pending proposals (grouped by unit and
proposer, aged — no expiry, settled #18, G49) · corrections first if any retraction occurred · parked/asks past N days · needs-attention: idle tasks + unconfirmed/
dateless end dates (G56) + unreachable PICs (G69) ·
overload flags · a **project-wide section** (team-less tasks + project policies, G48) appended
to every team digest. Digests are dashboard views per team (settled #20); a lead may paste one
into their group by hand — humans relay, the bot never posts. Plus: **quote the freshest
team-scoped wrap note verbatim** (attributed + cited) — the leads' numbers ride along without a
metrics engine. Optional stretch: named counters (`volunteers 26/30`) as append-only points with
receipts; no formulas.

## Reasoning views

Task popup: grounded summary (decisions + updates + citations only) · list newest→oldest with
maker/time/status · **show-inactive toggle** (superseded AND rejected, badged with the rejection reason — withdrawn / overruled / veto / dismissed — incl. challenges)
· click any entry → state reconstructed at that `ts` (event-time replay) · dual stamps shown when
`recorded_at` differs. Team/project policy log = the same view filtered by scope.

## Eval & ops profiles

- Gate: decision precision ≥ 0.9 · linkage accuracy ≥ ~0.8 · **citation completeness on planted
  boundary cases** (D2) · golden set = the corpus's actual production windows (same corpus +
  same N ⇒ same windows), incl. flush tails and transcript-as-window; a few small slices kept as
  unit cases only.
- `EXTRACTION_BATCH_SIZE`: demo profile ~25 (visible incremental extraction), eval/CI 100
  (production shape). Documented in the runbook; not to be "fixed" on stage.
- `ORG_TIMEZONE` (G54; demo: `Asia/Ho_Chi_Minh`): all week bucketing, day-count lamps, digest
  scheduling, and relative-date resolution ("CN này", "thứ 6") compute in org time; storage
  stays timezone-aware UTC.
## Phase impact (delta)

- **Phase 0 seed:** `user_teams` + `role_rank` map + linh-as-coordinator + parties (chi Yen,
  InTheXanh, ward office, school IT, sound vendor) + `tasks.kind` on planted tasks +
  **two projects**: "Charity Fair 2026" campaign (aiv-events + aiv-comms groups, end 2026-08-02)
  and "Weekend Classes" program (aiv-education group, end_date null) — one group ↔ one project,
  cross-linked where needed by campaign↔program dependency edges. Corpus
  rework: add task refs to some markers (both marker forms tested), relabel golden set to
  production windows.
- **Phase 1:** decision spine per this doc (ops/facets, lifecycle transactions, resurrection,
  change-of-mind withdrawal), windows incl. bulk-flush + context tail + ledger, update lanes,
  corroboration lane (G66), eval gate above.
- **Phase 2:** capture-side chat lanes (approval replies + reacts on source messages, markers),
  dashboard feed + approver inbox (proposals, challenges, retractions, radar), reaction acts
  (G67) + membership truth (G69), per-team digest views, speaker-map upload flow.
- **Phase 3:** dashboard as before + policy log + party grouping + show-inactive.

## Accepted gaps (settled #15 — recorded, not forgotten)

| # | Gap | Why accepted | Workaround on record |
|---|---|---|---|
| G61 | No decision-churn detection between equal-rank leads (S40) | Needs ≥2 peer leads sharing a unit + sustained conflict — niche in a 10-person NPO; every flip is already surfaced with receipts and listed in the digest | Coordinator supersession apex + digest visibility; one GROUP BY away if real usage shows churn |
| G64 | No "in-negotiation" proposal state (S43) | A fourth lifecycle branch (+ nudge suppression + UI) to pause one reminder; nothing breaks without it — pending IS the truth of a negotiation | Haggle in-thread; approve-of-revision sweeps the sibling; dismiss-stale silences nudges |
| G68 (residual) | Out-of-room utterances about another project's task are never born effective, any rank (S47) | Covering it means cross-project authority evaluation inside every window, to save one tap; "which room can change my task" staying predictable is worth more | Foreign-linked content arrives as a routed proposal in the owning side's inbox/digest — one approval tap effects it (or decide in the owning room; the relay lane also works) |

## Deferred (roadmap slide)

Real auth (platform login — `platform_user_id` is the bridge) · bi-temporal queries · rule
engine (TD2's "overrun needs sign-off") · metrics engine beyond counters · additional chat
adapters through the same platform contract (Slack/Discord export) · voice transcription ·
multi-step approval chains · general delegation grants.

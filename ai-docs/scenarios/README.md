# Scenario verification — gap register

End-to-end scenario traces against `../design-v2.md`. Two batches:

- **S1–S5** (2026-07-18, first batch): fictional cast derived from the review's xlsx canon
  (Director "An", IT head "Joe", Jack/Minh…). Model-level findings; still valid.
- **S6–S15** (second batch): grounded in the **real synthetic corpus** (`data/` — AIV NPO,
  10 personas, 3 channels, 532 msgs + transcript), with exact window math counted per channel.
  ⚠ Name collision: corpus `an` is a comms *member* — unrelated to S1–S5's fictional director.
  The corpus cast is authoritative for the demo (settled decision #7).

| Report | Scenario | Complexity |
|---|---|---|
| [S1](S1-assign-jack.md) | Authorized assignment in chat | ★ |
| [S2](S2-jack-completes.md) | Completion reported in plain chat | ★ |
| [S3](S3-apple-overruled-by-peach.md) | Proposal overruled; supersession authority | ★★ |
| [S4](S4-cross-team-dependency-slip.md) | Cross-team dependency slip, radar, escalation | ★★ |
| [S5](S5-wrong-decision-veto.md) | Wrong decision goes effective; veto | ★★ |
| [S6](S6-tshirt-lifecycle.md) | T-shirt lifecycle: D6→B4 across two channels | ★ |
| [S7](S7-policy-decisions-no-task.md) | Policy decisions with no task (D5/D7/D8/TD2) | ★★ |
| [S8](S8-invisible-blocker-b1.md) | Implicit blocker across windows (B1) | ★★★ |
| [S9](S9-window-cuts-venue-thread.md) | Window boundary mid-supersession-thread (D1→D2) | ★★★★ |
| [S10](S10-transcript-never-fires.md) | Transcript below threshold (TD1/TD2/TB1) | ★★★★ |
| [S11](S11-chi-yen-ghost.md) | Departed member still blocking two teams | ★★★★ |
| [S12](S12-digest-vs-human-wrap.md) | Computed digest vs the leads' hand-written wraps | ★★★★ |
| [S13](S13-matrix-org-no-root.md) | Multi-team members; no root in the hierarchy | ★★★★★ |
| [S14](S14-one-project-or-two.md) | Project vs ongoing program; group exclusivity | ★★★★★ |
| [S15](S15-full-replay-audit.md) | **Full replay scored against the answer key** | ★★★★★ |
| [S16](S16-fair-day-and-after.md) | Run 1a: project end / close-out | ★★★★ |
| [S17](S17-storm-sunday-duplicate-map.md) | Run 1b: policy exception + task merge | ★★★★ |
| [S18](S18-relay-race-undo.md) | Run 2a: relay, race, undo — **clean** | ★★★★ |
| [S19](S19-crunch-week-new-volunteer.md) | Run 2b: crunch week + unknown volunteer | ★★★★★ |
| [S20](S20-misinformation-challenge.md) | Run 3a: rumor, challenge, asks — **clean** | ★★★★ |
| [S21](S21-double-hat-khoa.md) | Run 3b: matrix load, peer tie — **clean** | ★★★★★ |
| [S22](S22-new-season.md) | Run 4a: project succession, archive — **clean** | ★★★★★ |
| [S23](S23-outage-day.md) | Run 4b: LLM outage resilience — **clean** | ★★★★ |
| [S24](S24-edited-evidence.md) | Run 5a: edited/deleted source messages | ★★★★ |
| [S25](S25-contract-is-a-photo.md) | Run 5b: media messages & forwards | ★★★ |
| [S26](S26-september-quiet-months.md) | Run 5c: programs between seasonal projects | ★★★★★ |
| [S27](S27-nobodys-team-task.md) | Run 5d: team-less task governance | ★★★ |
| [S28](S28-overeager-volunteer.md) | Run 5e: proposal spam / hygiene | ★★★ |
| [S29](S29-ok-chot-reply.md) | Run 6a: terse reply-decisions, approval-by-reply | ★★★★ |
| [S30](S30-fair-needs-the-kids.md) | Run 6b: seasonal ↔ org-level dependencies | ★★★★ |
| [S31](S31-approved-too-late.md) | Run 6c: stale approvals, terminal-state locks | ★★★★ |
| [S32](S32-group-upgrade-silent-bot.md) | Run 6d: chat-id migration, kicked bot, timezone | ★★★ |
| [S33](S33-status-ping-pong.md) | Run 6e: contested status between PICs | ★★★ |
| [S34](S34-zombie-todo-program.md) | Run 7a: dateless/idle work in programs | ★★★ |
| [S35](S35-fair-moves-a-week.md) | Run 7b: rescheduling the campaign end date | ★★★★ |
| [S36](S36-talking-back-to-the-bot.md) | Run 7c: replies to bot posts, self-ingestion | ★★★★ |
| [S37](S37-booth-changes-hands.md) | Run 7d: cross-project task transfer | ★★★★ |
| [S38](S38-khoa-split-week.md) | Run 7e: two-project composite — **clean** | ★★★★ |
| [S39](S39-merge-eats-itself.md) | Run 8a: merge × dependencies self-loop — fixed | ★★★ |
| [S40](S40-peer-lead-decision-war.md) | Run 8b: equal-rank decision churn — **accepted** | ★★★ |
| [S41](S41-provisional-vanishes.md) | Run 8c: pruning a provisional with holdings — fixed | ★★★ |
| [S42](S42-escalation-lands-where.md) | Run 8d: cross-boundary escalation routing — fixed | ★★★ |
| [S43](S43-proposal-negotiation.md) | Run 8e: proposal under negotiation — **accepted** | ★★★ |
| [S44](S44-approved-then-edited.md) | Run 9a: edit races an approval — fixed | ★★★★ |
| [S45](S45-echo-of-a-decision.md) | Run 9b: restatements need a corroboration lane — fixed | ★★★★ |
| [S46](S46-the-thumb-that-decides.md) | Run 9c: reaction acts — storage, withdrawal — fixed | ★★★★ |
| [S47](S47-wrong-room-right-task.md) | Run 9d: cross-room targeting — fixed + **accepted** residual | ★★★★ |
| [S48](S48-left-the-group-not-the-org.md) | Run 9e: left the group, not the org — fixed | ★★★ |

## Blockers — break a stated rule, lose data, or kill a hero demo beat

| # | Gap | From | One-line fix |
|---|---|---|---|
| G7 | Plain-chat PIC progress has no path in (violates PIC carve-out) | S2 | Extraction emits proposed `task_updates`; auto-apply iff cited author is PIC |
| G10 | Lower rank can supersede a superior's decision (violates review §III) | S3 | Supersede requires `rank(actor) ≥ rank(old maker, snapshotted)` else `proposed` |
| G17 | Rejection doesn't resurrect the superseded predecessor → silent facet loss | S5 | Inverse transaction: restore predecessor iff no other effective superseder |
| G26 | Decisions require a task; most planted decisions are **policies** → hero Q&A #3 dead | S7 | Decision scope: `task(s) \| team \| project`; linkage adds TEAM/PROJECT_POLICY |
| G27 | Weak signals can't accumulate across windows → hero implicit blocker B1 missed | S8 | Persistent signal ledger; promote on corroboration; citations = all mentions |
| G29 | Bulk sources < 100 msgs never extract → fair date/budget/permit never exist | S10 | Bulk sources flush on upload completion (upload = window) |

## High

| # | Gap | From | One-line fix |
|---|---|---|---|
| G1 | Assignment payload lacks add/remove/set ops (multi-PIC fold ambiguous) | S1 | Explicit ops; bare assign = add; set/remove require supersession link |
| G3 | Authority circular for NEW_TASK | S1 | Check against the chat group's team |
| G8 | Batch latency: lamps/digest assert what chat already contradicts | S2 | Flush-before-read (digest + radar); markers as instant lane |
| G13 | Every PIC musing becomes a proposed decision → approval spam | S3 | Consistent-with-effective → note update; only contradiction escalates |
| G14 | Nothing scheduled reads the lamps → blockers still surface late | S4 | Daily radar job; dedup + escalate (PICs day 1, LCA day 3) |
| G19 | `confidence` consulted by nothing → authorized joke goes effective | S5 | Threshold gate; below it born `proposed`, author self-confirms 👍 |
| G22 | External-wait blockers lost v1's `waiting_on/since/owner` structure | S6 | Restore structured fields on blocked state; radar keys off `since` |
| G23 | Cross-channel workstream → duplicate team-scoped tasks | S6 | Linkage candidates = project's open tasks (team's listed first) |
| G28 | Evidence in window k−1 unciteable by decision in window k (D2 receipts fail) | S9 | Read-only context tail (cite-only, never re-extract) + ledger |
| G31 | Late-arriving history (transcripts) breaks arrival-order assumptions | S10 | Fold/supersede by event `ts`; add `recorded_at`; older same-facet → born superseded |
| G32 | External parties are strings → risks never aggregate (chi Yen ×2 teams) | S11 | `parties` table + alias match; `waiting_on` FK; radar groups by party |
| G33 | No user lifecycle → no offboarding sweep (the founding pitch!) | S11 | `users.status` + departing sweep generating reassignment proposals |
| G36 | `users.team_id` single — cannot represent khoa/thao/minh → Phase-0 seed unbuildable | S13 | `user_teams {user, team, role_in_team}` join |
| G37 | No root: LCA/rank comparison are partial functions → escalation + G10 gate break | S13 | Seed linh as coordinator (corpus-faithful) + rootless fallback rules |
| G38 | Project rules assume dated projects; ongoing programs break defaulting/exclusivity | S14 | `tasks.kind: project\|ongoing` (demo); project-as-optional-scope (roadmap) |
| G40 | Golden set (8–20-msg slices) ≠ production windows (~100) → eval gate invalid | S15 | Relabel golden set as the corpus's actual windows + flush tails |

## Medium

| # | Gap | From | One-line fix |
|---|---|---|---|
| G4 | No pre-assignment overload gate in chat | S1 | Post-hoc warning; silence = acceptance, noted on decision |
| G5 | Pending proposals invisible to the group | S1 | Bot announces "📋 Proposed … awaiting @approver" |
| G9 | Non-PIC completion reports unhandled | S2 | Lanes: PIC auto · authority decision-grade · others PIC-confirm 👍 |
| G11 | Zombie proposals after facet decided | S3 | Effective-write sweeps same-facet proposals → rejected(overruled) |
| G12 | "Overruled by" narrative unrepresentable | S3 | Reuse `superseded_by_decision_id` on the rejected proposal |
| G15 | Stored `blocked` vs derived lamp contradict | S4 | Blocked requires reason; unblock ping asks PIC; render chip + lamp apart |
| G16 | Weak-signal→blocked pipeline entity-less; `requested` edges underspecified | S4 | Proposed `task_update`; only `confirmed` edges lamp; expiry to digest |
| G18 | Anyone can veto anything | S5 | Maker or rank ≥ maker rejects; others file a challenge |
| G20 | No retraction messaging after veto | S5 | Threaded correction post; next digest leads with corrections |
| G24 | Bare (v1-style) markers — the corpus's own — have undefined linkage | S6 | Record instantly; attach via linker (candidates/NEW_TASK/triage) |
| G25 | In-chat delegation ("minh chốt luôn nhé") invisible to the authority gate | S6 | Approval-by-prior-utterance: cite the authorizing message, born effective |
| G30 | Transcript speakers can't pass the authority gate (no telegram id) | S10 | Per-upload speaker map; unmapped → born `proposed` |
| G34 | Digest computes thinner than the leads' hand wraps (metrics homeless) | S12 | Quote team-scoped wrap notes in digest; counters = stretch |
| G39 | batch=100 makes the replay a 4-beat demo | S15 | Demo profile `EXTRACTION_BATCH_SIZE≈25`; eval/CI at 100 |

## Low

| # | Gap | From | One-line fix |
|---|---|---|---|
| G2 | Projection joins read as writable tables | S1 | Mark as derived |
| G6 | Assignment ≠ status transition unstated | S1 | State orthogonality |
| G21 | Rejected decisions' popup visibility unspecified | S5 | "Show inactive" toggle, badged |
| G35 | Parked topics ("để sau") evaporate | S12 | Ledger `kind: parked`; digest line after N quiet days |

## What consistently held up

Append-only bodies + status-flip supersession (flawless even mid-boundary, S9) · attribution via
cited authors · marker lane (rescued D6 at a window boundary, S6) · linkage-candidates continuity
(no duplicate venue task, S9) · precision discipline on distractors (X1–X4 extract to nothing) ·
LCA routing and load computation (matrix-ready once G36/G37 land).

## Iteration runs (S16–S23) — converging design-v2 against reality

G1–G40 were folded into **design-v2 rev 2** (full rewrite); then scenario-pairs ran against the
current revision until two consecutive runs found nothing:

| Run | Scenarios | New gaps | Design response |
|---|---|---|---|
| 1 | S16, S17 | **G41** project lifecycle/close-out (HIGH) · **G42** `effect_window` exceptions to standing policies (HIGH) · **G43** task merge (MED-HIGH) | rev 3 |
| 2 | S18 ✓clean, S19 | **G44** no arrival lane for unknown senders → provisional users (HIGH) | rev 4 (+ proactive: transactional/idempotent windows, backlog-notice honesty) |
| 3 | S20 ✓clean, S21 ✓clean | — | — |
| 4 | S22 ✓clean, S23 ✓clean | — | — |
| 5 (probe) | S24–S28 | **G45** message revisions + pinned citations (HIGH) · **G46** media & forwards (MED-HIGH) · **G47** standing teams + org-level ongoing home (HIGH) · **G48** team-less task governance (MED) · **G49** proposal hygiene (LOW-MED) | rev 5 |
| 6 (probe) | S29–S33 | **G50** reply-target hydration + approval-by-reply (HIGH) · **G51** org-level dependency matrix (MED) · **G52** terminal-state locks + approval revalidation (MED-HIGH) · **G53** capture liveness & chat-id migration (MED-HIGH) · **G54** org timezone (LOW) · **G55** contested lamp + green-light retraction (LOW-MED) | rev 6 |
| 7 | S34–S38 (S38 ✓clean) | **G56** idle/dateless lamp + anchored warnings (MED) · **G57** project end_date facet + defaulted-date cascade (MED-HIGH) · **G58** outbound registry + self-ingestion exclusion (MED) · **G59** cross-project transfer op (MED) | rev 8 |
| 8 (adversarial, triaged per settled #15) | S39–S43 | FIXED: **G60** merge self-loops (LOW-MED) · **G62** holdings-aware pruning (MED) · **G63** escalation routing (MED). ACCEPTED: **G61** peer-lead churn detection · **G64** in-negotiation state | rev 9 — zero open unaccepted gaps |
| 9 (adversarial #2 — contract-verb sweep) | S44–S48 | FIXED: **G65** approvals bind to the seen revision (MED) · **G66** corroboration lane + same-value guard (MED-HIGH — TD-2's `corroborated_by` was unproducible) · **G67** reaction acts: storage, instant apply, withdrawal (MED-HIGH) · **G69** group membership ≠ org + delivery reachability (LOW-MED). PARTIAL: **G68** cross-room targeting — foreign-candidate lane FIXED, effective-out-of-room ACCEPTED | rev 12 (atop the #17/#18 directives) — zero open unaccepted gaps |

**Convergence status:** rev 4 achieved two consecutive clean runs (3–4) on coordination
semantics. The user-requested probe run 5 then targeted **new territory** — the platform
boundary (Telegram edits/deletes, media, forwards, marker spam) and two structural leftovers of
the G38/G41 shortcuts (programs between seasons, team-less governance) — and found 5 gaps, all
absorbed in **rev 5**. Probe run 6 hunted the *seams between recent fixes* (threads vs windows,
the G47 bucket vs the rev-2 dependency validator, deferred approvals vs a moving world) plus
platform ops and multi-PIC contention — 6 more gaps, absorbed in **rev 6**. In both probe runs,
previously-verified areas did not re-break; finds keep coming from genuinely new territory,
and their average severity is declining (run 1 of the S1–S15 era: 6 blockers; run 6: none).
Run 7 (first under the rev-7 constraints: platform-generic, one group ↔ one project) probed the
two-project world's own mechanics — program watchfulness, campaign rescheduling, the bot's own
messages, and cross-project transfer: 4 gaps, **all MEDIUM-grade — first run with no HIGH** —
plus one clean composite (S38). Adversarial run 8 (S39–S43, triaged per settled #15) added
G60–G64: three fixed, two accepted with rationale. Adversarial run 9 (S44–S48) swept the
**contract verbs themselves** — react/un-react, an edit racing an approval, membership-leave —
plus the restatement and wrong-room seams, and found the **act-evidence layer** under-modeled:
reactions had no storage, approvals no revision binding, restatements no output type (that one
the `data-v2` answer key already punishes — TD-2's `corroborated_by` was unproducible). The
decision core did not re-break; all four fixes reuse standing machinery (revisions, outbound
registry, proposal lane, G63 routing). Clean-run counter remains reset. Register: **G1–G69 —
every gap either fixed in `../design-v2.md` or recorded in its §Accepted gaps (G61 · G64 ·
G68-residual).**

**Direction (2026-07-18, post run 6 → rev 7):** scenario verification stays **platform-generic**
— the core models a plain chat platform (send / reply / emoji-react / edit / media / membership
events); platform quirks like S32's chat-id migration are adapter concerns and out of scenario
scope going forward. And **one group ↔ one project is permanent**: rev 7 recast G47's
standing-team/org-level machinery into **program projects** (`projects.end_date` null =
ongoing program; dated = campaign) — corpus seed becomes two projects: "Charity Fair 2026"
(aiv-events, aiv-comms) and "Weekend Classes" (aiv-education), linked by campaign↔program
dependency edges where needed.

**Direction (2026-07-18, post run 8 → rev 10):** two user directives on the proposal lifecycle,
absorbed without a scenario run (settled #17). **(a) Proposals expire:** 48h unapproved →
`rejected(expired)`; the bot threads a notice onto the proposal's announcement ("expired,
rejected — renew?"), and the proposer's 👍 flips it back to `proposed` with a fresh 48h.
Replaces the open-ended 48h re-nudge. **(b) Change-of-mind replaces:** a proposer's own
different-value proposal on the same unit withdraws their older pending one
(`rejected(withdrawn)`, linked to the newer); parallel pendings now always mean *different*
proposers. Ripples into earlier traces (kept as historical records): S18's
approve-after-two-days now lands on the expiry boundary (renew path), S31's 3-day-late approval
is bounded away (≤48h; G52 still guards inside the window), S28's ignored queue self-clears at
48h, S43's accepted negotiation workaround now rides the renew loop, and an unresolved
peer-conflict hold defaults to the standing decision after 48h (with notices). No new G numbers
(directives, not scenario finds); clean-run counter stays reset; the next run should probe both
rules.

**Direction (2026-07-18, final — settled #18 supersedes #17a):** **proposals never expire.** A
`proposed` decision stays open until a human act resolves it — approval, explicit deny/veto/
dismiss, a same-unit effective write (overruled — an act, not a clock), or the proposer's own
change-of-mind withdrawal (#17b stands). No TTL, no `approval_deadline`, no `rejected(expired)`,
no renew loop. Anti-rot is visibility: the 48h approver nudge is restored, pendings list (aged)
in every digest, approvers keep bulk dismiss-stale. The expiry ripple-claims in the previous
note (S18 renew path, S31 bounding, S28 self-clearing, S43 renew loop, peer-hold defaulting)
are **void**; those scenarios stand as originally traced. This also de-risks the fixtures the
TTL had put in play: D-13's 8-day approval gap (m0054→m0088) and D-11's 18-minute sweep margin
are non-issues again.

**Direction (2026-07-18, final — settled #20):** **the bot never posts to groups.** Capture is
read-only; all output moves to the dashboard (per-persona feed, approver inbox, team digest
views); humans relay to chat when needed (a lead pastes a digest — the bot never speaks). Voids
the chat-delivery mechanics in earlier traces: S36's reply-to-bot routing (no bot posts exist),
the announcement beats in S28/S31/S42/S46/S47, G5's in-group proposal announcement (→ inbox +
pending queue), G58's outbound registry (retired — nothing outbound to register), and G69's
delivery re-routing (narrowed to membership truth + an out-of-the-room flag). Chat approval
lanes survive on **source messages**: an affirmation reply or 👍 react on the proposal's own
message; the dashboard tap is the universal act. Scenario files stay as historical records;
the design text governs.

## Reality-check verdict (the question S6–S15 answer)

The **decision lifecycle core is right** and survived every test. What the corpus disproves is
the *assumption layer*: every decision has a task (S7) · every blocker a predecessor (S6) · every
signal fits one window (S8) · every source reaches threshold (S10) · every person is a user (S11)
· one team per member, one root per org (S13) · every workstream has an end date (S14). Each is
contradicted by hand-verified ground truth, and each fix is at the seams — scope, ledger, flush
rule, join table, one column — leaving the specified lifecycle untouched. **S15's bottom line:
as designed, v2 scores 2/11 clean on planted decisions and 1/3 hero Q&A; with the register
applied, projected full coverage.**

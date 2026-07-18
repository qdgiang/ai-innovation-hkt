# Work split — two concurrent implementers + one merge gate

> Task division for parallel implementation. Phase content, order, and test gates are
> unchanged from [`plan.md`](plan.md) — this doc only assigns **who builds what**. Rule
> in force: an implementer owns a module **vertically** — its backend, its API routers,
> and its dashboard views — FE and BE of one module are never split across people.
> Where this contradicts plan.md's P4/P5 lane composition (which split BE vs FE),
> **this doc wins**; plan.md's checklists and exit gates still apply as written.
>
> **Claude is the final gate**: every PR is reviewed by Claude against design-v2 +
> data-model + the test gates, and Claude performs all merges to `main`.

## Module ownership (constant for the whole build)

| Module | Owner | Includes (FE too) | plan.md refs |
|---|---|---|---|
| `org` | **A** | seed loader, config ops, provisional-user write port; `/personas` API | P0, P2 (ING-6 port) |
| `llm` | **A** | gateway client, retry, validation, call ledger | P2 |
| `ingestion` | **A** | windows, markers, hydration, extraction, linkage, signals-emit, speaker maps; eval harness (OPS-3) | P2, P3 |
| `decisions` | **A** | the core + universal command gateway; **FE:** decision/policy logs (DSH-4), proposal forms + the shared typed command client (DSH-7, EVM-021 envelope) | P1, P3 (acts) |
| `knowledge` | **A** | retrieval + truth-state Q&A; **FE:** Q&A box (DSH-6) | P5, P6-track 7 |
| `api` shell | **A** | app assembly, `POST /commands` front door, persona scoping middleware (module routers stay with their module owners) | P4 |
| `connectors` | **B** | message store, replay, Telegram (T2), capture health; **FE:** transcript upload flow, health banners (DSH-8) | P2, P3 (CAP-3), P6-track 1 |
| `tasks` | **B** | the fold, lanes, dependencies, terminal locks, dates, time-travel; **FE:** task board + reasoning popup (DSH-3) | P1, P6-track 4 |
| `signals` | **B** | ledger, promotion, radar lamps, overload, escalation; **FE:** blocker board (DSH-5 half) | P2 (ledger v0), P3 (promotion), P4 |
| `surfacing` | **B** | feed, inbox, digests, close-out, on/offboarding; **FE:** feed + inbox views (DSH-2), digest views (DSH-5 half) | P4, P6-tracks 2/3/5 |
| `scheduler` | **B** | job definitions (radar, digest, nudges, self-check) | P4 |
| frontend shell | **B** | Next.js app scaffold, layout, persona switcher UI (DSH-1; data from A's `/personas`) | P0, P4 |
| `db` + migration 0001 | **A** | after 0001, each owner migrates their own tables; the gate renumbers on merge | P0 |
| `infra` + CI | **B** | compose, Caddy, Makefile, CI workflows, L0 fixture tests | P0 |
| `contracts` | **shared, gated** | command/event/type unions — see protocol below | every contract-first PR |

Track shapes: **A = the write spine** (org → decisions → ingestion → knowledge) — fewer
modules, the two hardest problems (decision core, extraction quality). **B = the
projection & surface** (connectors → tasks → signals → surfacing → all shell/infra) —
more modules, heavier FE, nothing XL. A's P2 eval-iteration time overlaps B's
connectors+FE buildout, which keeps the lanes level.

## Phase × owner matrix (content = plan.md's checklists)

| plan.md phase | A builds | B builds |
|---|---|---|
| **P0** | backend scaffold · migration 0001 · `org` v0 + seed | frontend shell · compose + CI · L0 fixture tests |
| **P1** | `decisions` DEC-1..9 + gateway (= P1 Lane A) + ING-7 birth-side ordering | `tasks` TSK-1/2/3/6/7/8 + event-consumer plumbing (= P1 Lane B; fold-side ordering) — fold tested against synthetic `domain_events` until A's gateway lands; command-driven L1 suites run at phase exit |
| **P2** | `llm` + ING-1..5 · ING-6 arrival lane (through A's own `org` port) · ING-8 + eval gate (OPS-3) | CAP-1 message store + CAP-2 replay + SIG-1 ledger v0 · may start DSH-1/DSH-3 skeletons (mock data — the read API freezes at P4) |
| **P3** | DEC-5 chat acts (replies, reactions, rev binding, revalidation) + corroboration extractor side | CAP-3 transcripts + upload FE · SIG-1 promotion + SIG-2 parties-consumption |
| **P4** | `api` shell + `POST /commands` + org/decisions routers · DSH-4 logs · DSH-7 command client | `surfacing` (feed/inbox/digest projections) + SIG-3/5 radar + `scheduler` · DSH-1/2/5 views + task board/popup (DSH-3) |
| **P5** | `knowledge` KNW-1/2 + DSH-6 Q&A box · L4 E2E smoke | finish dashboard: time-travel wiring, inbox taps via A's command client, receipts rendering, polish |
| **P6** | track 7 pgvector (others as capacity allows) | tracks 1 (Telegram+health), 2 (close-out), 3 (onboarding), 4 (merge/split/transfer — gateway ops reviewed by A), 5 (offboarding), 6 (overload) |
| **P7** | joint hardening; the gate runs the pre-demo checklist and freezes | joint |

## The A↔B interfaces (each frozen by a contract-first PR, gated)

1. **Message read port** (`connectors` → `ingestion`): B owns the message store; A's
   windows read it **via `connectors`' read-only service port** — never direct table
   access. (Standing rule of this doc; architecture.md's import list is silent on this
   pair and stays unchanged.)
2. **Command union** (`contracts.commands`): shapes of `RecordTaskUpdate`, `RecordSignal`,
   act commands — B's modules emit nothing; B's *UI* sends them via A's client; A's
   gateway processes all.
3. **`domain_events` catalog** (`contracts.events`): A appends, B's projections consume.
   Event shape changes are contract PRs, never silent.
4. **`org` port**: A owns; B's `signals` (party match) and `surfacing` read it.
5. **Read-API sketch** (architecture.md §API surface): per-module routers — each owner
   implements their own; the shell (A) mounts them. Freeze at P4 contract PR so B's FE
   never waits on A.
6. **Shared command client** (DSH-7): A ships the typed EVM-021 envelope client early in
   P4; B's inbox/board taps consume it — B never hand-rolls a write call.
7. **Transcript upload seam**: B parses + uploads (CAP-3), A resolves speaker maps +
   flushes windows; the upload event is the contract.
8. **Tracked-message registry** (`decisions` → `connectors`): reactions are recorded only
   on *tracked* messages — the source messages of pending records (G67). `decisions`
   exposes the tracked-id lookup; B's adapter consults it before writing `reaction_acts`.
9. **Task-state read port** (`tasks` → `decisions`): the gateway's update-lane routing
   ("is the cited author a PIC?") and G52 approval-time revalidation (terminal state,
   current values) read `tasks`' projection via its read-only port. (Standing rule of
   this doc; architecture.md's import list stays unchanged.)

## Gate & merge protocol (Claude)

- **Branching:** `feat/a-<module>-<topic>` / `feat/b-<module>-<topic>` off `main`; PRs
  target `main`; implementers never merge — **the gate reviews and merges every PR**.
- **Review bar per PR:** matches design-v2/data-model semantics (spot-check against the
  cited G#/EVM#) · carries its tests (testing-strategy rule 1) · PR CI green
  (L0·L1·L3·L2-recorded) · import-linter clean (module boundaries hold) · no
  contract/data-model drift smuggled in a feature PR.
- **Contract changes:** separate PR labeled `contract-change`, needs both implementers'
  review + the gate; frozen mid-phase per plan.md working agreement 1.
- **Collisions:** contract PRs merge first; migration files are renumbered by the gate at
  merge; two PRs touching one module means ownership was violated — the gate bounces the
  intruder (plan.md agreement 4).
- **Phase exits:** the gate runs the phase's full gate (incl. `eval-live` at P2/P3, L4 at
  P5) and explicitly opens the next phase; nobody builds ahead of an unopened phase
  (agreement 5).
- **Cross-module needs:** raised to the gate as an interface question (usually: the
  contract is wrong), never solved by importing the other track's internals.

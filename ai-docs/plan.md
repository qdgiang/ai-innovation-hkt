# Plan — EverMind implementation (from zero, against rev 13)

> Fresh build; the old scaffold is deleted. Feature IDs → [`features.md`](features.md),
> module shapes → [`architecture.md`](architecture.md), schema → [`data-model.md`](data-model.md),
> gates → [`testing-strategy.md`](testing-strategy.md).
>
> **Shape of the plan:** seven phases, each small enough to hold in one session, each with
> an explicit test gate. Phases P1–P5 have **two parallel lanes (A/B)** that touch disjoint
> modules, so two people (or two agent sessions) can work simultaneously with near-zero
> merge surface. Nothing in lane A blocks lane B inside a phase; phases themselves are
> sequential because each stands on the previous gate.

## Working agreements (read once, follow always)

1. **Contract-first.** The first PR of every phase changes only `contracts/` (+ API
   sketch when relevant) and is reviewed by both lanes before feature work starts. After
   that the contracts are **frozen for the phase** — changing them mid-phase requires both
   lanes' sign-off in the PR description.
2. **Main is always green.** Feature branches + PR; the PR CI set
   (L0·L1·L3·L2-recorded) must pass; no `--no-verify`, no gate-weakening (testing-strategy
   rule 2).
3. **A feature lands with its tests** — same PR. The scenario/gap id goes in the test
   docstring and the PR description.
4. **Module ownership per phase** is listed below; touching the other lane's module in a
   shared phase = coordinate first (it's usually a sign the contract is wrong).
5. **Don't build ahead.** T2 items wait until the T1 gate (end of P5) is green — a smaller
   finished system beats a larger broken one.

## Phase map

| Phase | Delivers | Features | Gate |
|---|---|---|---|
| P0 | Scaffold, schema, fixtures net | OPS-1/2, CAP-6 | L0 green in CI; migration applies |
| P1 | Decision core + task fold (pure domain) | DEC-1..9, TSK-1/2/3/6/7/8, ING-7 | L1 core suites green |
| P2 | Replay → windows → extraction → eval | CAP-1/2, ING-1..5, ING-8, SIG-1 (emit), OPS-3 | **L2 gates pass** @ batch 25 & 100 |
| P3 | Acts, transcripts, signals promotion | DEC-5 (chat acts), CAP-3, ING-6, SIG-1/2, TSK — remaining L1 | L1 full suite green |
| P4 | Surfacing + API + dashboard shell | SRF-1/2/3, SIG-3/5, OPS-4, DSH-1/2/3 (read), api | L3 green; dashboard shows replay state |
| P5 | Q&A + dashboard writes + hero path | KNW-1/2, DSH-4..7 | **L4 green**; hero demo rehearsed |
| P6 | T2 à-la-carte (independent tracks) | CAP-4/5, TSK-4/5, SRF-4/5/6, SIG-4, KNW-3, DSH-8 | per-track tests |
| P7 | Hardening, deploy, demo ops | — | pre-demo checklist |

---

## P0 — Foundation (both together; half a day)

- [ ] Backend scaffold per `architecture.md` layout: `pyproject` (uv), module skeletons,
      `contracts/` enums + base types from `data-model.md`.
- [ ] `infra/docker-compose.yml` (db w/ pgvector + healthcheck) + `Makefile`
      (`dev/test/eval/seed/replay/demo`) + `infra/.env.example`.
- [ ] Alembic migration 0001 = the full data-model (including plumbing tables).
- [ ] `ops` seed loader: `data-v2/org.json` → org tables (OPS-1, CAP-6 binding, [D5] keys).
- [ ] L0 fixture-integrity tests + CI workflow (PR matrix from `testing-strategy.md`,
      including the v2-only guard and import-linter config).
- [ ] Frontend: `create-next-app` shell only (builds in CI; no views yet).

**Exit:** `make dev` brings up db + api skeleton (`/healthz`); `make seed` loads the org;
CI runs L0 green on a PR.

## P1 — The pure domain core (the longest phase; no LLM, no platform anywhere)

**Contract-first PR:** `contracts.commands` + `contracts.events` (full union), reviewed by
both lanes.

**Lane A — `decisions` module:**
- [ ] DEC-1 store + lifecycle states + append-only trigger.
- [ ] DEC-2 facet registry (`unit_key` derivation; the design-v2 §Facet table as data, not ifs).
- [ ] DEC-3 effective-write transaction (flip + sweep + same-value guard G66 + `effective_units`).
- [ ] DEC-4 authority (`can_decide` total, rank gate, delegation, rootless fallback,
      peer-hold; at-act snapshot [EVM-005]).
- [ ] DEC-6 rejection/challenge/resurrection · DEC-7 hygiene (merge, #17b withdrawal, bulk) ·
      DEC-8 effect-windows (+overlap hold [EVM-004]) · DEC-9 multi-op [EVM-003].
- [ ] `processed_commands` idempotency + expected-version check [EVM-021].

**Lane B — `tasks` module + event plumbing:**
- [ ] `domain_events` append + `projection_offsets` consumer loop (the D3 spine).
- [ ] TSK-1 fold (tasks + derived assignment/team joins; multi-PIC slots; `parent_task_id`).
- [ ] TSK-2 update lanes (PIC auto / authority / confirm-card stub) · TSK-6 terminal locks.
- [ ] TSK-3 dependencies (DAG check, G51 matrix, requested/confirmed/needs-rewire [EVM-006]).
- [ ] TSK-7 date governance (defaulting, flags, [D4] kind rules) · TSK-8 time-travel replay.
- [ ] ING-7 late-arrival ordering (tiebreak [EVM-012], born-already-superseded).

**Tests (split by lane, listed in `testing-strategy.md` L1):** lifecycle basics ·
policies/scopes · supersession/windows · hierarchy/matrix · proposal hygiene ·
ordering/late-arrival · multi-op · write plumbing · invariants (autouse).

**Exit:** those L1 suites green; a scripted S3 run (apple→peach) reproduces the trace
end-to-end through commands only.

## P2 — Ingestion spine + the eval gate (the make-or-break phase)

**Contract-first PR:** extractor output schema (candidates/updates/signals/corroborations)
+ window/materialization tables.

**Lane A — windows + LLM:**
- [ ] CAP-1 message store (revisions, media kinds, `raw_ref`) + CAP-2 replay connector
      (instant + paced).
- [ ] ING-2 windowing (high-water, batch N, flush-on-upload hook, flush-before-read,
      transactional/idempotent, backlog notice) + ING-3 hydration.
- [ ] `llm` gateway (retry/backoff, schema validation, call ledger) + ING-8 injection frame.
- [ ] ING-4 extraction prompts v1 + OPS-3 eval harness (`eval-live`/`eval-recorded`,
      report file, both batch profiles).

**Lane B — deterministic lanes:**
- [ ] ING-1 markers (grammar incl. `T-…` refs, grace-window amend, materialization dedup
      [EVM-002]).
- [ ] ING-5 linkage resolver (candidate assembly incl. foreign index; UNLINKED triage;
      G68 never-effective routing).
- [ ] SIG-1 signal emission + ledger identity key [EVM-013] (promotion logic lands P3).
- [ ] ING-6 provisional-user arrival (G44) + holdings-aware pruning stub (G62).

**Exit (the go/no-go the old plan called "let's see if it works"):** `make eval` passes
every L2 gate at batch 25 **and** 100, live. If precision won't converge after a solid
iteration block: narrow scope to marker-weighted capture (the deterministic lane carries
the demo) and re-plan — that decision is made *here*, never on stage.

## P3 — Acts & the remaining domain lanes

**Lane A — chat-side acts (DEC-5):**
- [ ] Affirmation/negation reply lane (phrase list first, LLM for ambiguity; G50).
- [ ] Reaction acts: tracked-message recording, instant apply, grace revert, post-grace
      challenge (G67).
- [ ] Revision binding (`rev_at_act`, edit-race → proposed+diff; G65) + approval-time
      revalidation (G52).

**Lane B — bulk sources + promotion:**
- [ ] CAP-3 transcript connector + ING-6 speaker maps (G29/G30) + uploads versioning
      [EVM-011].
- [ ] SIG-1 promotion (≥2 or 1+staleness → proposed blocked / requested edge, citations =
      all mentions) + SIG-2 parties + blocked structure.
- [ ] Corroboration lane end-to-end (extractor → citation append; TD-2 fixture proves it).

**Exit:** L1 full suite green (acts/evidence, cross-room, terminal/stale, signals, users
lifecycle modules included); eval still green (re-run — prompts changed).

## P4 — Surfacing + API + dashboard reads (FE lane starts here in earnest)

**Contract-first PR:** the REST read surface (OpenAPI from the `architecture.md` sketch) —
after this freezes, FE needs nothing from BE but a running container.

**Lane A (backend):**
- [ ] SRF-1 feed projection (batching, dedup, retraction append) + SRF-2 inbox + receipts
      [EVM-022].
- [ ] SIG-3 radar job + lamps + SIG-5 escalation routing + OPS-4 scheduler (+48h nudge,
      G54 timezone).
- [ ] SRF-3 digest views (all sections incl. wrap-note quote, aged pendings, needs-attention).
- [ ] `api` read routers + `POST /commands` envelope + persona scoping.

**Lane B (frontend):**
- [ ] DSH-1 shell + persona switcher (+ the "modeled, not enforced" honesty note).
- [ ] DSH-2 feed + inbox views.
- [ ] DSH-3 task board + reasoning popup (read-only first: log, show-inactive, dual
      stamps, citation badges; time-travel wired to `GET /tasks/{id}/at`).
- [ ] DSH-5 digest + blocker-board views.

**Exit:** L3 green; `make demo` (seed + instant replay) then browsing the dashboard shows
the corpus's end-state faithfully — decisions, folds, lamps, digest, inbox.

## P5 — Knowledge + writes + the hero path

**Lane A:**
- [ ] KNW-1 structured retrieval + KNW-2 truth-state Q&A (+ citation-completeness
      post-check) + `POST /qa`.
- [ ] L4 E2E smoke automated (recorded mode) — the hero assertions from
      `testing-strategy.md`.

**Lane B:**
- [ ] DSH-7 write lane: proposal form, approve/dismiss/confirm taps, expected-version +
      command-id client [EVM-021], capture receipts surfaced.
- [ ] DSH-4 decision/policy/task logs with the stakeholder search+filter matrix.
- [ ] DSH-6 Q&A box.

**Exit (T1 done):** L4 green end-to-end; paced replay rehearsed by a human once — markers
fire, windows extract, D-10 supersedes on screen, B-2 promotes, transcript flushes, three
hero Q&A answer with receipts, one dashboard approval completes the loop. The bot posted
nothing.

## P6 — T2 à-la-carte (independent tracks; pick by remaining time)

Each track is self-contained with its own tests; skipping any leaves T1 intact. Suggested
order by demo value:

1. **Live Telegram** — CAP-4 read-only connector + CAP-5 capture health + DSH-8 banners
   (runbook: BotFather privacy-mode OFF before joining; no backfill — replay covers
   history; no-send guard test).
2. **Close-out + retrospective** — SRF-4 (G41; the institutional-memory closer).
3. **Onboarding brief** — SRF-5 (the rotation beat; cheap: it's a filtered read).
4. **Merge/split/transfer** — TSK-4/5 (already designed; L1 tests exist from P1 — this
   track wires commands + UI).
5. **Offboarding sweep** — SRF-6.
6. **Overload guard** — SIG-4 (bounded per EVM-017).
7. **pgvector retrieval** — KNW-3 (only if hero Q&A shows recall misses).

## P7 — Hardening + demo ops

- [ ] Deploy runbook: VPS + compose `prod` profile + Caddy; `pg_dump` cron; `make export`.
- [ ] Demo script (beats + timings + who clicks what) + fallback plan (recorded eval
      report + instant-replay screenshots if the venue network dies).
- [ ] Freeze: no schema/prompt changes after the last live eval; tag the demo commit.

## Risks & standing mitigations

| Risk | Mitigation |
|---|---|
| Extraction precision doesn't converge | P2 gate is early and explicit; marker lane is a full deterministic fallback; provider swap is env config |
| The domain core is bigger than it looks | It's front-loaded (P1) with no LLM to blur it; the facet registry is data-driven; L1 tests are written per-feature, not after |
| Two-lane merge friction | Module ownership + contract-first + frozen interfaces per phase |
| Demo-day live LLM wobble | Paced replay is pre-warmed; markers are instant; eval-recorded proves the pipeline without network; digest/Q&A pre-run morning-of |
| Scope creep re-opening settled debates | `features.md` product rules + data-model "explicitly NOT in schema" list; re-litigating requires a new settled ruling in design-v2 |
| Windows dev environment quirks | Everything runs in compose; host needs only Docker + node + uv |

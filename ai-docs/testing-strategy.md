# Testing strategy — EverMind

> The regression net. The rule the whole plan hangs on: **a phase is done only when every
> layer below is green, and a feature ships only with the tests that pin it.** This
> operationalizes the EVM-008/D7 work order (three test layers; core tests platform-free;
> fixtures v2-only) and extends it to five layers.
>
> The 48 scenario traces (`scenarios/`) and the gap register (G1–G69) are not documentation
> — they are the test backlog. Every gap that was FIXED gets a test that fails if the fix
> regresses.

## The five layers

| Layer | Name | Needs | Runs on | Speed |
|---|---|---|---|---|
| L0 | Fixture integrity | nothing (pure file checks) | every PR | seconds |
| L1 | Domain scenario suite | Postgres (compose) — **no LLM, no network** | every PR | fast |
| L2 | Extraction eval | LLM (live) or recorded responses | PR (recorded) · nightly + pre-demo (live) | minutes |
| L3 | API & architecture contracts | Postgres | every PR | fast |
| L4 | E2E demo smoke | full compose + LLM (or recorded) | pre-merge to main · pre-demo | minutes |

### L0 — Fixture integrity (guards `data-v2/`)

- `corpus.jsonl`: every `id` equals its line number (`m0001..` = line N); globally
  time-sorted; exactly one `kind:"photo"` (m0100); marker strings (`!decision`, `!blocked`)
  appear **only** in the inventoried messages (m0003, m0009, m0041, m0085).
- `answer_key.json` ↔ corpus: every cited message id exists; `window_map_batch25` matches
  the deterministic window math at N=25, and the batch-100 shape (flush-only) also
  validates; TT=89/CL=29 counts hold.
- `org.json`: all referenced users/teams/groups/parties resolve; **trang is absent** (she
  must arrive provisionally — G44); linh is coordinator; matrix members (khoa, thao) have
  multiple `user_teams` rows.
- Transcript: 30 turns, `[MM:SS] Name:` shape, attendee header parses; 30 < any batch
  threshold (the flush-on-upload guarantee stays meaningful).
- **Same-commit rule (enforced socially, checked mechanically):** if `corpus.jsonl` changes
  in a PR, `answer_key.json` must change in the same PR (CI fails otherwise).
- **v2-only guard:** CI greps the codebase for references to the deleted v1 `data/` path —
  any hit fails (EVM-008's drift can never restart).

### L1 — Domain scenario suite (the crown jewel)

Pure domain tests: scripted **commands/events in → asserted state out**, against real
Postgres, with zero LLM and zero platform code. This is where the 48 traces become
executable. Structure `backend/tests/scenarios/` by cluster:

| Test module | Derived from | Pins |
|---|---|---|
| `test_lifecycle_basics.py` | S1, S2, S3, S5 | born-effective gates, PIC lane (G7), rank gate (G10), sweep→overruled (G11/G12), veto + resurrection (G17/G18), confidence gate (G19) |
| `test_policies_and_scopes.py` | S7, S27 | team/project scope (G26), team-less governance (G48), `can_decide` total |
| `test_supersession_and_windows.py` | S9, S17 | append-only flips mid-thread, effect-window shadowing (G42), overlap → hold [EVM-004], exception never supersedes |
| `test_signals_ledger.py` | S8, S12 | cross-window accumulation (G27), promotion rules, parked/asks aging (G35), identity key [EVM-013] |
| `test_hierarchy_matrix.py` | S13, S21 | user_teams matrix (G36), rootless fallback (G37), peer-conflict hold, LCA routing |
| `test_projects_programs.py` | S14, S26, S34 | campaign vs program [D4], `kind=ongoing` exemptions, idle lamp (G56), close-out untouchability (G47) |
| `test_lifecycle_project.py` | S16, S22, S35 | closing/closed sweeps (G41), retrospective content, reschedule cascade (G57), new-season-new-group (#13b) |
| `test_users_lifecycle.py` | S11, S19, S41, S48 | provisional arrival (G44), holdings-aware pruning (G62), offboarding sweep (G33), group-leave ≠ departure (G69) |
| `test_merge_split_transfer.py` | S37, S39 | merge re-pointing + DAG re-check (G43/G60), husk redirect, split w/ `parent_task_id` [EVM-014], two-key transfer + revalidation (G59) |
| `test_terminal_and_stale.py` | S31, S33 | terminal locks + revalidation-at-approval (G52), contested lamp (G55), green-light retraction, only-done satisfies + needs-rewire [EVM-006] |
| `test_proposal_hygiene.py` | S28, S43 | dedup-merge (G49), change-of-mind withdrawal (#17b), bulk acts, **no expiry ever** (#18: assert a 30-day-old proposal is still `proposed` after every job runs) |
| `test_acts_evidence.py` | S44, S45, S46 | rev binding `rev_at_act` (G65), edit-race → proposed+diff, corroboration lane + same-value guard (G66), reaction acts incl. grace revert & post-grace challenge (G67) |
| `test_cross_room.py` | S47, S30, S4, S42 | foreign linkage never-effective (G68), dependency matrix (G51), escalation per-endpoint cards (G63) |
| `test_ordering_late_arrival.py` | S10 (order half), S15 | event-ts fold, born-already-superseded (G31), tiebreak [EVM-012], dual stamps |
| `test_multiop_atomicity.py` | EVM-003 | all-or-nothing, highest-authority routing |
| `test_write_plumbing.py` | EVM-021, EVM-002 | command idempotency (same id twice ⇒ one event), expected-version mismatch ⇒ 409+diff, materialization dedup |
| `test_invariants.py` | data-model §invariants | the 10 cross-cutting invariants as property-style sweeps over every other test's end-state (autouse fixture) |

Conventions: one scenario step = one command; asserts read projections (`tasks`,
`feed_entries`, `inbox_items`) — not internals — so refactors don't shred the suite. Each
test's docstring cites its scenario/gap ids: when one fails, the failure message points at
the business rule, not just the assert.

### L2 — Extraction eval (`make eval`)

Replay `data-v2` through real windowing → real extraction → real linkage, score against
`answer_key.json`.

**Gates (from design-v2 §Eval; a red gate blocks the phase, not the commit):**

| Metric | Gate |
|---|---|
| Decision precision | ≥ 0.90 |
| Decision recall | report (target ≥ 0.7; precision wins conflicts) |
| Linkage accuracy | ≥ 0.80 |
| Citation completeness on planted boundary cases | 100% (D-03 approval m0088 cites m0054 via hydration; B-2 cites all three mentions) |
| Corroboration | TD-2 gains `corroborated_by: [m0109]` — produced, not a duplicate decision (G66) |
| Distractors X-1..X-4 | extract to **nothing** (incl. the authorized joke X-3 gated by τ) |
| Marker lane | 4/4 marker records, correct linkage, zero duplicates on window re-run [EVM-002] |

**Two profiles** (both must pass): `EXTRACTION_BATCH_SIZE=25` (demo shape, windows at
TT#25/50/75+tail, CL#25+tail) and `=100` (prod shape, flush-only) — same corpus, same key.

**Two modes:** `eval-live` (real LLM; nightly + before any demo; writes
`eval-report.json` — checked in, so drift is visible in diffs) and `eval-recorded`
(response fixtures recorded from a passing live run; deterministic; runs on every PR).
Re-record when prompts/models change — a PR that changes a prompt without re-recording
fails loudly.

### L3 — API & architecture contracts

- Command envelope: validation, persona stamping, `client_command_id` round-trip.
- Read endpoints: filter matrix from the stakeholder spec (time/PIC/team/status/type;
  decision search by id/context/description), persona scoping, `show_inactive`.
- Time-travel endpoint returns the S15-verified reconstruction.
- **Import-linter** contract: module dependency rules from `architecture.md` (`tasks`
  imports only `contracts`; `decisions` only `contracts` + `org`; nothing imports `api`;
  LangChain appears only under `knowledge`).
- **No-send guard:** the Telegram adapter's test asserts the client object exposes no
  send/post method (settled #20 enforced structurally) and CI greps `sendMessage|send_message`
  out of `connectors/`.

### L4 — E2E demo smoke

Full compose up → seed → **instant** replay (pace 0) → transcript upload → assert the hero
path end-state: 15 chat decisions + 3 transcript records with expected statuses (D-10
superseded D-03; D-11 `rejected(overruled)` by D-12; DC-05 windowed under DC-01), 10 tasks
with expected folds, B-2 promoted with 3 citations, trang provisional, digest views render
with corrections/pending/aged sections, the three hero Q&A return expected receipts, one
dashboard approval flips a pending proposal and produces feed entry + receipt. Then the
paced profile is smoke-run manually before any live demo (it's the show itself).

## CI matrix

| Trigger | Runs |
|---|---|
| Every PR | L0 · L1 · L3 · L2-recorded · import-linter · lint/type (`ruff`, `mypy` light) |
| Merge to main | PR set + L4 (recorded LLM) |
| Nightly / manual | L2-live (fresh `eval-report.json`) · L4-live |
| Pre-demo checklist | L2-live · L4-live · paced replay by hand |

## Regression rules (the contract with future sessions)

1. **A feature PR carries its tests.** New lifecycle behavior → L1 test; new prompt →
   re-recorded L2; new endpoint → L3. No test, no merge.
2. **Never weaken a gate to ship.** If precision drops below 0.9, the prompt/model changes
   until it doesn't — or the change reverts. Gate changes are a design decision (log in
   design-v2's settled table), not a CI edit.
3. **Fixtures are contracts.** `answer_key.json` changes only with corpus changes,
   hand-verified, same commit (L0 enforces).
4. **Scenario files are frozen history** — new behavior gets new tests, old tests get
   updated only when a settled ruling changes the expected outcome (cite the ruling # in
   the diff).
5. **The suite is the spec's shadow.** When a future session is unsure what a rule means,
   the L1 test for its G-number is the executable answer.

# Fix plan — complete MVP/demo (2026-07-18)

Goal: close every gap found in the "run and check" pass so the dashboard demos
the full product story: corpus replay → decisions/tasks/updates through the
command gateway → live board, decision log, feed/inbox, blockers, digest, Q&A —
with a working persona switcher and dashboard write path (approve/reject,
status changes).

## Context — what was wrong

- FE persona switcher was a hardcoded 3-item array, never wired to
  `GET /personas`; live fetches sent `X-Persona: 1` (an invalid handle → 400 →
  pages silently rendered empty).
- `/decisions` and `/qa` pages were "coming in P5" placeholders; backend
  `GET /decisions` and `POST /qa` raised `NotImplementedError`.
- Sidebar "Memory capture active" badge was hardcoded, never called
  `GET /health/capture`.
- No write UI: `api.postCommand` was an unused placeholder.
- Projection-consumer loop and APScheduler were defined but never started —
  commands appended `domain_events` but the board never updated.
- Nothing folded decision events into feed/inbox (no surfacing consumer).
- `TasksService.get_task_view` (interface #9) was missing → gateway ran
  port-less → PIC auto-apply lane broken.
- No extraction (ING, P2) → replayed chat never became decisions/tasks →
  every page empty.
- No CORS middleware → any browser-side call to the API would fail.
- FastAPI app: no lifespan wiring at all.

## DONE — backend

1. **`GET /decisions`** (`backend/evermind/api/routers/decisions_router.py`)
   Full filter matrix: `scope` (target `task:2` or kind `task`), `q` (ilike over
   description/context/note), `from_`/`to` (ts), `user` (handle or id),
   `show_inactive` (adds superseded/rejected), `limit`. Rows carry citations
   (`{message_id, kind}`), maker/approver handles, effect_window, supersession
   links.

2. **LLM gateway** (`backend/evermind/llm/client.py`)
   `LLMGateway.call_json(system, user, schema)` — OpenAI-compatible client from
   env (`AI_BASE_URL`/`AI_MODEL`/`AI_API_KEY`), temperature 0, JSON extraction
   (fences/braces), schema validation with ONE retry-with-error, then raises
   `LLMUnavailable`. Logs model/tokens/latency.

3. **Knowledge Q&A** (`backend/evermind/knowledge/service.py` + `knowledge_router.py`)
   KNW-1/2: keyword-scored structured retrieval over decisions (+citations),
   tasks, and the cited chat messages verbatim; truth-state labels (superseded →
   names successor, proposed → pending, effect windows dated). LLM composes the
   cited answer; **graceful fallback** to structured-only rows when the LLM is
   unavailable. Response: `{answer, sources[], llm, cited_decision_ids,
   cited_task_ids, cited_message_ids}`.

4. **App lifespan** (`backend/evermind/api/main.py`)
   - Background thread polls `TasksConsumer` + `SurfacingConsumer` every
     `CONSUMER_POLL_MS` (default 2000 ms; 0 disables — tests).
   - Starts the APScheduler (`build_scheduler`) when `RUN_SCHEDULER=true`.
   - CORS middleware (allow all — demo posture) so browser-side calls work.
   - New settings in `config.py`: `consumer_poll_ms`, `run_scheduler`.

5. **Surfacing consumer** (`backend/evermind/surfacing/consumer.py`, NEW)
   Folds decision-lifecycle events into feed/inbox (own
   `projection_offsets` row "surfacing"):
   - `decision_proposed` → inbox `proposal` item per approver (deduped)
   - `decision_effective` → resolves open proposal items ("approved"); feed
     entries for maker/approver/newly-assigned PICs
   - `decision_rejected` → resolves items ("rejected"); feed entry for the
     notified author
   - `task_update_pending_confirm` → inbox `confirm` card per PIC
   - `challenge_filed` → inbox `challenge` for the maker

6. **Tasks glue** (`backend/evermind/tasks/`)
   - `service.py`: added `get_task_view` (interface #9, `contracts.ports.TaskView`)
     + `teams_of` — the gateway now routes PIC-auto vs authority vs
     confirm-card correctly.
   - `consumer.py`: `status: blocked` updates now set
     `blocked_waiting_on_party_id/text` (from payload) + `blocked_since`
     (event ts); leaving blocked clears them → blockers board/digest work.

7. **Demo seeder** (`backend/evermind/demo.py`, NEW)
   Stands in for the unbuilt LLM extraction: replays `data-v2/answer_key.json`
   ground truth through the REAL gateway (`DecisionsService.handle`) as
   commands, folding projections after each. Idempotent via deterministic
   `client_command_id` = uuid5("evermind-demo:<key>") [EVM-021].
   - Also runs org seed + corpus replay first (both idempotent) — one command
     brings up the whole demo.
   - Creates **trang** as provisional user (G44), handle `trang`, confirmed by
     linh at the D-09 approval beat.
   - Story includes: marker policies (D-01, DC-01), 10 task-creating decisions,
     member-proposal→lead-approval (D-03, D-09, D-13), budget sweep
     (D-11 proposed → overruled by D-12), supersession (D-03 → D-10), windowed
     exception DC-05 shadowing DC-01, transcript records TD-1/TD-2,
     dependencies DEP-1/DEP-2, 12 task updates incl. the U-06 blocker
     (waiting on Kim Long, party-resolved) and its U-07 resolution, and one
     **live pending proposal** (`DEMO-P1`, huong → linh's inbox) for the
     dashboard approve beat.
   - `--until m0100` stops mid-story (T-02 still blocked → blockers radar has
     content); rerunning without it plays to the final state.
   - Run inside api container:
     `python -m evermind.demo /tmp/org.json /tmp/corpus.jsonl [--until m0100]`

## DONE — frontend

8. **Types** (`frontend/lib/types.ts`): `Decision`, `QAResponse`,
   `CaptureGroupHealth`; `Persona` now has `handle`/`status`.

9. **API client** (`frontend/lib/api-client.ts`): real `postCommand` (surfaces
   409 body), typed helpers `approveProposal` / `rejectProposal` /
   `recordTaskStatus` / `askQA`.

10. **Persona plumbing** (`frontend/lib/persona.ts` server + `persona-client.ts`
    client): cookie `evermind_persona`, default `linh`.

11. **Topbar** (`components/shell/Topbar.tsx`): switcher fed by `GET /personas`
    (fetched in `app/layout.tsx`, passed as props), writes the cookie +
    `router.refresh()`; shows name + rank, "không xác thực — demo" badge.

12. **Sidebar** (`components/shell/Sidebar.tsx`): `CaptureStatusCard` polls
    `GET /health/capture` every 30 s — green/amber(dark group)/grey(unreachable).

13. **Layout** (`app/layout.tsx`): async server component — fetches personas,
    reads persona cookie, passes both to Topbar.

14. **Feed page** (`app/feed/page.tsx`): uses cookie persona for `/feed` +
    `/inbox`; feed entries show payload description + decision/task links;
    inbox proposal/challenge items link to `/decisions`, confirms to the task.

15. **Decisions page** (`app/decisions/page.tsx`, rewritten): live list with
    filter form (q, user, show_inactive), status chips, citations, effect-window
    + supersession labels, related-task links, and `DecisionActions`
    (`components/decisions/DecisionActions.tsx`) approve/dismiss buttons on
    proposed rows (acting as the switcher persona).

16. **Q&A page** (`app/qa/page.tsx`, rewritten): client page → `POST /qa`;
    3 suggested questions (from answer_key `qa_questions`); answer + D/T/m
    citation chips + collapsible retrieved-sources list; honest banner when the
    LLM fell back to structured-only.

17. **Task status write UI** (`components/tasks/TaskStatusSelect.tsx`, NEW):
    per-card status dropdown → `RecordTaskUpdate` command; shows non-applied
    outcomes (e.g. `pending_confirm`) inline.

18. **Task board write UI wired** (`app/tasks/page.tsx`): fetches `/personas`
    alongside `/tasks` (persona from cookie), builds `personaUserIds`
    (handle → id) map; cards are divs with the Link on the title +
    `<TaskStatusSelect>` below; blocked cards show "⏳ waiting on …" from
    `blocked_waiting_on_text` (falls back to `party #id`).

19. **Digest decisions sections** (`app/digest/page.tsx`): fetches
    `GET /decisions?show_inactive=false` (persona from cookie) next to the
    digest; "Quyết định & chính sách" = recent effective decisions (top 6,
    windowed exceptions flagged in violet); "Đang chờ duyệt" = proposed
    decisions with age ("chờ N ngày trước"); rows link to `/decisions`;
    the "owner A (needs decisions)" TODO footnote is gone.

20. **Upload page persona** (`app/upload/page.tsx`): free-text persona input
    dropped; uses `personaFromDocument()` (cookie handle).

## TO DO (remaining — run on the server, not locally)

21. **Verify end-to-end in the running stack** (containers already up from the
    earlier bring-up; api/frontend bind-mount source so most changes hot-reload;
    `config.py` change requires api restart):
    ```sh
    # full reset is SAFEST (schema unchanged, but demo determinism):
    docker compose -f infra/docker-compose.yml restart api
    docker cp data-v2/org.json infra-api-1:/tmp/org.json
    docker cp data-v2/corpus.jsonl infra-api-1:/tmp/corpus.jsonl
    export MSYS_NO_PATHCONV=1
    docker compose -f infra/docker-compose.yml exec -T api \
      python -m evermind.demo /tmp/org.json /tmp/corpus.jsonl
    ```
    Then check (all with `-H "X-Persona: linh"`):
    - `GET /decisions?show_inactive=true` → ~20 rows, statuses match answer key
      (D-10 effective, its D-03 twin superseded, D-11 rejected/overruled,
      DC-05 windowed effective, DC-01 still effective, DEMO-P1 proposed)
    - `GET /tasks` → 11 tasks (10 story + none for DEMO-P1 until approved);
      final statuses per answer key (T-01/05/06/C1/C2/C3 done, T-02/03/04/07
      doing)
    - `GET /feed` + `GET /inbox` per persona (linh's inbox: DEMO-P1 proposal)
    - `GET /blockers?by=party` (empty at final state; `--until m0100` shows
      Kim Long) and `GET /digest/1`
    - `POST /qa` with the 3 suggested questions (needs the AI key to produce
      prose; fallback must still return cited rows)
    - `POST /commands` approve of DEMO-P1 as linh → task appears on board
    - FE pages: switch persona → feed changes; approve from /decisions;
      change a task status from the board.
    - Watch `docker compose logs api` for consumer-loop errors.

22. **Tests/linters in container** (runbook §4): `pytest -q`, `ruff check .`,
    `mypy evermind`, `lint-imports`. Note: the test suite wipes tables —
    re-run the demo seeder afterwards. New code to watch: `evermind.demo`
    (top-level module — not covered by import-linter contracts, deliberate),
    surfacing consumer, lifespan thread (`CONSUMER_POLL_MS=0` disables it for
    tests if any interfere).

## PIVOT (2026-07-18, later): knowledge-base workspace UI (frontend_ref)

The Feed/Inbox page layout was rejected — `frontend_ref/` is the desired
product shape. Implemented:

- **BE `workspace_router.py`**: `GET /projects` + `GET /workspace/{id}` — one
  bundle (project, teams, members+roles+PIC load, tasks with pics/deps/facts/
  decision ids, serialized decisions, evidence receipts with typed backlinks,
  counts). Facts fold attr:* ops from TaskDecisionLog.
- **BE fix — approval loses task-creation context**: `_approve` emitted
  `decision_effective` without `new_task_id`/`project_id`, so tasks born via
  member-proposal→approval landed in project 0 (T-02 invisible to the
  workspace). New `decisions.new_task_id`/`context_project_id` columns stamped
  at propose time, re-emitted at approval. Columns ALTERed into the live DB;
  task 2's project_id healed by hand. Full reset still pending (see below).
- **FE rebuilt as the workspace**: `app/page.tsx` renders
  `components/workspace/WorkspaceApp` (full app-shell in `app/workspace.css`
  = ref styles + additions): sidebar (KB / Task & decisions / Decision log /
  Evidence archive / Blocker radar + projects + capture card + persona
  switcher in the profile row), topbar (⌘K search, bell = pending inbox),
  metric strip, 4 view tabs + radar, right inspector (task: state facts,
  dependencies, decision lineage w/ show-inactive, receipts; decision:
  outcome, supersession links, affected tasks, receipts, **approve/reject**),
  evidence modal (quote, rev, locator, backlinks), Ask EverMind modal (/qa).
  Feed/Inbox pages are out of the nav (still routable).
- **Still pending (user-run)**: DB reset + reseed so the NEW_TASK authority
  fix takes effect (T-C1/2/3 born effective, single pending proposal
  DEMO-P1). After reset the ALTERed columns are covered by create_all.

## Known gaps / decisions taken (document honestly in the demo)

- **DC-04 relay nuance dropped**: mai decides directly (non-relayed). Reason:
  approving a NEW_TASK proposal requires task-team authority, but the task
  isn't in the projection until effective → `_authorize_decision_targets`
  falls to apex-only → mai's self-confirm would be `forbidden`.
  **Partially FIXED (live-verify pass)**: the born-effective lane now
  authorizes against the PRE-rewrite targets, so `_can_decide_new_task`
  (G3: group's team lead+) actually fires — without this, mai's T-C1/T-C2/
  T-C3 stayed `proposed`, 3 tasks never existed, and linh's inbox held 4
  stray proposals. The APPROVAL path (`_authorize_decision_targets`) still
  sees rewritten `task:` targets → apex-only; fine for the demo (linh
  approves everything).
- **Signals ledger not seeded** (X-1 parked, B-2/B-3 signal mentions): there is
  no signals consumer folding `signal_recorded` events into the `signals`
  table, and no FE surface reads raw signals. Blockers demo rides on task
  `status:blocked` instead. Future: `signals/consumer.py` mirroring the other
  two consumers.
- **Extraction (ING) still unbuilt** — the seeder IS the stand-in; the demo
  story says "extraction output" and every row genuinely went through the
  gateway.
- **⌘K search button** in Topbar was dropped with the redesign (was decorative).
- Corpus timestamps are Sept 2026 (future vs. today 2026-07-18) → commands are
  gateway-stamped "now" (passing corpus ts would trip the impossible-chronology
  triage). Ordering is preserved by emission order; message citations keep the
  corpus dates.

## File inventory (this change)

Backend: `api/main.py`, `api/routers/{decisions_router,knowledge_router}.py`,
`llm/client.py`, `knowledge/service.py`, `surfacing/consumer.py` (new),
`tasks/{service,consumer}.py`, `config.py`, `demo.py` (new).

Frontend: `lib/{types,api-client,persona,persona-client}.ts`,
`components/shell/{Topbar,Sidebar}.tsx`,
`components/decisions/DecisionActions.tsx` (new),
`components/tasks/TaskStatusSelect.tsx` (new),
`app/{layout,feed/page,decisions/page,qa/page,tasks/page,digest/page,upload/page}.tsx`.

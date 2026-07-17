# Plan — phased build

> Each phase is independently shippable and demoable. Stop after any phase and you still have a coherent story. Feature IDs reference `features.md`. Effort estimates assume one experienced data engineer; treat them as relative sizes, not promises.

## Phase map

| Phase | Outcome | Complexity | Est. effort | Demo-able as |
|-------|---------|-----------|-------------|--------------|
| 0 | Scaffold + synthetic corpus + golden set | Low | 0.5–1 day | — (foundation) |
| 1 | **Proof of concept**: files in → records out → digest in terminal | Medium | 1–1.5 days | "The pipeline works — with receipts" |
| 2 | Live Telegram bot: capture, `/ask`, digest posting | Medium | 1 day | End-to-end live demo in a real group |
| 3 | Web dashboard + blocker radar + scheduler | Medium–High | 1.5–2 days | The full judge-facing product |
| 4 | Polish + stretch: onboarding brief, corrections, Notion, deploy | Varies | pick-and-choose | The winning 3-minute demo |

Cut line: **Phase 2 is the minimum for the hackathon demo.** Phase 3 is where it starts looking like a product. Phase 4 items are ranked à-la-carte.

## The 48-hour clock

The hackathon window is **48h**; the estimates above are calendar-day sizes for the full scope. Mapped onto the clock:

| Hours | Work | Notes |
|-------|------|-------|
| Pre-hackathon | Author the synthetic corpus + answer key + golden set; create the BotFather bot; open Vercel/Railway accounts | **If rules allow prep.** The corpus is a creative artifact, not code — front-load it. If prep isn't allowed, it becomes H0–H6 with heavy LLM assist. |
| H0–H6 | Phase 0: scaffold, contracts, corpus loaded | |
| H6–H20 | Phase 1: extraction spine + eval gate | The go/pivot decision (marker-weighted fallback) fires at **~H20**, not "after a day" |
| H20–H30 | Phase 2: live bot + FastAPI + first Railway deploy | ← cut line; everything after this is upside |
| H30–H42 | Phase 3: Next.js dashboard (decision log + blocker board first), blocker radar, scheduler | Ship views in priority order; stop when the clock says so |
| H42–H48 | Freeze deploys, demo script, rehearse twice, sleep buffer | Phase 4 items only if rehearsal is already solid |

Rule of thumb: anything not demoable by H42 gets cut, not finished.

---

## Phase 0 — Foundation (Low, ~0.5–1 day)

Goal: everything later phases stand on. No AI calls yet except authoring help.

- [ ] Repo scaffold: `backend/` (FastAPI skeleton), `ai/` (empty modules + schemas), `ingestion/`, `data/`, `infra/` (docker-compose with Postgres), `frontend/` (defer init to Phase 3).
- [ ] Freeze the three contracts (`Message`, `Record`, `Citation`) as Pydantic models + SQL DDL. **F1**
- [ ] Author the synthetic Telegram corpus (~4–6 weeks, 3 teams, ~10 personas) **with an answer key**: plant ~8 decisions (2 superseding pairs), ~5 blockers (1 buried/implicit), weekly statuses. Include some `!decision`/`!blocked` markers and plenty of unmarked ones. **F2 input**
- [ ] Author 1 fake physical-meeting transcript (~15 min of speaker turns, 2 decisions + 1 blocker planted). **F3 input**
- [ ] Label the golden set: ~20 conversation windows → expected records. **F6 input**

Exit criteria: `docker compose up db` works; corpus + answer key committed; contracts reviewed.

Risk note: corpus authoring looks like a side task but **is the demo** — don't rush it. LLM-assist the drafting, hand-verify the answer key.

## Phase 1 — Proof of concept: the spine (Medium, ~1–1.5 days) ← "let's see if it works"

Goal: prove extraction quality on seeded data before investing in anything live. Terminal-only, SQLite is fine.

- [ ] F1 store + F2 replay adapter + F3 transcript adapter (CLI: `ingest replay data/corpus.jsonl`, `ingest transcript data/meeting-.txt`).
- [ ] F5 marker path (regex → records, deterministic).
- [ ] F4 passive extraction: windowing, DeepSeek JSON-output call (`deepseek-v4-flash`, OpenAI-compatible SDK) + Pydantic validation with retry, dedup, citations. Iterate the prompt **against the golden set**.
- [ ] F6 eval harness: `make eval` → precision/recall per record type printed.
- [ ] F7 (minimal) digest: `make digest` → Markdown to stdout with citations.
- [ ] Smoke Q&A (F8 minimal): `make ask Q="why did we switch venues?"` → cited answer in terminal.

Exit criteria (the "does it work" gate):
- Decision extraction ≥ ~0.9 precision on the golden set (recall ≥ ~0.7 acceptable).
- Digest renders with a citation on every line.
- Q&A answers the 3 planted "rotation questions" correctly with citations.

Decision point: if extraction precision won't converge after a day of prompt iteration → pivot weight toward the marker path (F5) and reframe as "structure-assisted capture" — the demo story survives.

## Phase 2 — Live Telegram (Medium, ~1 day)

Goal: the same pipeline, live. This is the minimum hackathon demo.

- [ ] F9 bot: long-polling worker → ingestion endpoint; `/ask` → F8; `/digest` on demand; scheduled digest post.
- [ ] Bot setup runbook: BotFather token, **disable privacy mode before adding to group**, demo group creation. Rehearse from scratch once.
- [ ] Backend: move from CLI calls to FastAPI endpoints (`POST /ingest/messages`, `GET /digest`, `POST /ask`); workers and CLI both use them.
- [ ] Postgres migration (swap SQLite; contracts unchanged).
- [ ] Replay-mode demo script: pipe corpus in "live" while the audience watches records materialize.

Exit criteria: in a fresh Telegram group — bot joins, someone types a blocker-ish message, `/digest` shows it; `/ask` answers a seeded question with a citation; digest auto-posts.

## Phase 3 — Product surface (Medium–High, ~1.5–2 days)

Goal: judge-facing polish + the remaining Demo-tier features.

- [ ] F10 blocker radar: staleness SQL + weak-signal flags; alert posts to channel. Tune thresholds on the corpus.
- [ ] F11 dashboard: **Next.js on Vercel (decided 2026-07-17).** Under the 48h clock, cut scope by dropping views, not by switching stacks.
  - Views in priority order: ① decision log w/ search + citations, ② blocker board w/ age, ③ digest archive, ④ Q&A box.
- [ ] Scheduler: weekly digest cron + daily staleness check (APScheduler in the worker, or cron in the container).
- [ ] Deploy per `deployment.md` so the demo doesn't run off a laptop.

Exit criteria: a judge with the URL can browse decisions, click a citation, see the blocker board, and ask a question — with zero explanation from you.

## Phase 4 — À-la-carte polish (pick by remaining time)

Ranked by pitch-impact per effort:

| Rank | Item | Effort | Why |
|------|------|--------|-----|
| 1 | **F12 onboarding brief** (`/onboard design`) | S–M | The volunteer-rotation hero beat; cheap because it re-filters existing records |
| 2 | **Demo script + seeded rehearsal** | S | The 3-min narrative: chaos → digest → rotation Q&A → blocker alert → sustainability close. Rehearse twice. |
| 3 | **F13 correction loop** (👎 to reject) | S | One-line answer to "what if the AI is wrong?" — live-demoable |
| 4 | **F14 Notion archive** | S–M | "The tool is disposable, the memory is not" — sustainability slide made real |
| 5 | Cost + handoff one-pager | S | NPO judges reward "<$10/mo, one container, handoff doc" |
| 6 | Embeddings/pgvector retrieval for Q&A | M | Only if keyword retrieval demonstrably misses on the corpus |
| 7 | Slack-export adapter (2nd source through same contract) | M | Proves platform-agnosticism; only if everything above is done |

---

## Standing risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Extraction precision doesn't converge | Phase 1 gate + marker-path pivot (decided by end of Phase 1, not on stage) |
| Telegram config failure on stage (privacy mode, token) | Runbook + rehearsed fresh setup + replay mode as fallback demo |
| Scope creep into platform-building | The cut line is written down; Phase 4 is explicitly optional |
| Live LLM latency/flake during demo | Deterministic siblings for every beat (markers, staleness SQL, pre-warmed digest); pre-computed fallback outputs committed to the repo |
| Solo bandwidth | Phases are strictly ordered; nothing in Phase N requires Phase N+1 knowledge |

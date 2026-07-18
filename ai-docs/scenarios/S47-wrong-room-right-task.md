# S47 — Wrong room, right task: cross-room talk about another project's work

**Run 9d (adversarial #2). Complexity: ★★★★**
Contract features used: send, reply. Settled #13 (one group ↔ one project) is NOT challenged
here — the group→project mapping stands. The question is what happens to the *content* people
inevitably utter in the wrong room. Multi-project people (mai, khoa, thao) live in both rooms;
the corpus itself already shows TT business discussed in CL (the DEP-2 pair, m0065/m0067).

## Grounding

Live, **`aiv-classes`** (G-CL → P-CL). The TT event program is decided: văn nghệ thiếu nhi
opens **19:00** (all-hands [01:31], effective, task *văn nghệ* in P-TT). mai (rank 2, **lead of
TEAM-ED only** — no authority in P-TT) posts in the classes group:

> "à khoa, vụ đêm hội — cô tính cho các bé lên **18:45** thay vì 19:00 nhé, đỡ trễ giờ ngủ"
> khoa: "dạ, để em báo bên trung thu"

## Trace

CL window fires. Candidates (rev 9): "**the project's** open tasks (group's team first) + the
target scopes' existing effective policies/attrs + open signals" — all scoped to **P-CL**. The
P-TT văn nghệ task and its 19:00 decision are *not in the candidate set*. The utterance is
unambiguous decision-shaped content about a task the extractor cannot see. Exhaustive outcomes:

| Branch | What happens | Why it fails |
|---|---|---|
| (a) link to the nearest CL task — rehearsal (T-C3-ish, semantically adjacent) | `attr:start-time=18:45` lands on the **rehearsal** task, announced in CL | Wrong unit mutated. TT never hears; rehearsal record now carries event-night trivia. Active damage. |
| (b) `NEW_TASK` in P-CL: "văn nghệ 18:45" | Phantom duplicate of a P-TT task, in the wrong project | Duplicate + wrong home; the real task's 19:00 stands uncontested. Active damage. |
| (c) `UNLINKED` → triage | Best case — a human sorts it | But the triage card's re-home options are *also* project-scoped; no path attaches it to a P-TT task. Dead ends politely. |

The authority layer never even engages (mai has none in P-TT, so nothing would go effective —
small mercy), but every linkage branch either damages a record or drops real content.

## What holds up ✅

- **Dependency-shaped cross-project talk works** — that's exactly the lane G51 built (DEP-2:
  campaign↔program edge, signals + upstream-lead confirm). Sequencing across projects: covered.
- **The social workaround exists and the corpus models it:** khoa relays into the TT group
  ("chị mai đề xuất 18:45") → relay lane + self-confirm (DC-04 pattern) handles it perfectly.
  The gap fires only when nobody relays — which is precisely when memory matters.
- **Settled #13 itself**: nothing here needs group↔project remapping. The mapping is fine; the
  *candidate scope* is the consequence that bites.

## Gap

### G68 — out-of-room content about another project's task mis-scopes (MEDIUM) → **PARTIAL FIX + ACCEPT (residual)**

- **Current:** linkage candidates are hard-scoped to the group's project; cross-project content
  links wrong, duplicates, or dead-ends in triage.
- **Expected (real world):** say a thing about the event in the classes room and the event side
  still hears about it — or at minimum, no record gets corrupted.
- **FIX (the damage-prevention half — cheap, reuses G63 + proposal lane):**
  1. Candidates gain a **slim foreign index**: id + title of OTHER active projects' open tasks
     (cite-only weight, listed after own-project candidates).
  2. Linkage may return **`task_id@foreign-project`** → such decisions are **never born
     effective**, regardless of rank: born `proposed`, routed to the target project's authority,
     **announced in the target project's own group** ("đề xuất từ aiv-classes cho task của bạn —
     duyệt?") via the G63 posting pattern. One 👍 there (S46 lane) makes it effective —
     approval always happens *in the room that owns the task*.
  3. Low-confidence foreign match → `UNLINKED` triage, whose card now offers foreign tasks as
     re-home targets (one tap).
- **ACCEPT (residual, recorded per settled #15):** out-of-room utterances are *never* effective
  on arrival — even from the coordinator. Cost of covering it: cross-project authority
  evaluation inside every window for a case one 👍 already closes. Workaround: decide in the
  owning room, or tap the routed proposal. Predictability of "which room can change my task"
  beats the saved tap.

## Verdict

The one-group-one-project simplification is sound; its unguarded edge was the linker's
tunnel vision. With the foreign-candidate lane, wrong-room content degrades to a well-routed
proposal instead of a corrupted record — and the accepted residual is one thumb-tap of
friction, in exchange for every task having exactly one room where decisions can go effective.

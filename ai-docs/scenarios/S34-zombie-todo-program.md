# S34 — The task that never starts (run 7a, vs rev 7)

> Hunt target: **rev 7's program projects have no clock — do any lamps still watch them?**
> Platform-generic; one group (aiv-education) ↔ one project (Weekend Classes program).
> Complexity ★★★.

## Scenario

In the Classes program (no project end date): mai creates "làm bộ giáo án Scratch nâng cao"
(advanced curriculum) on 07-05, no PIC volunteers, no dates set (`kind=ongoing`-adjacent
one-off inside a program). Six weeks pass. Nobody mentions it again. Separately, two fair tasks
sit with `end_date_defaulted=true` that nobody ever confirmed.

## Trace against rev 7

1. **The curriculum task's lamp coverage, one by one:** `overdue` — needs an end date; it has
   none (program tasks are exempt from defaulting, and there is no project end to default from
   anyway). Never fires. `late-start` — needs a date window. Never fires. `stale` — defined as
   *in-doing* with no events; this task is `todo`. Never fires. `blocked/at-risk` — no
   dependencies. `contested` — no flips. **Six weeks of silence and every lamp is dark.** In a
   campaign, the countdown eventually catches everything; in a program there is no countdown —
   rev 7 removed the clock (correctly) without replacing the watchfulness.
2. **The unconfirmed defaults:** the deadline rule says defaulted dates carry "a warning until
   a human confirms" — but *where does the warning live*? It's not in the digest skeleton
   (decisions/blockers/lamps/proposals/parked/asks — no dateless/unconfirmed line), and the
   radar's lamp list doesn't include it. A rule with no surface.
3. Real-world expectation (and the review's own line — "cảnh báo nếu task chưa có end date"):
   unstarted, undated, unowned work is exactly the kind that silently dies in NPOs; the system
   exists to keep it visible.

## What holds up ✅

- The *decision* to exempt program tasks from defaulting is right (S16/S26 proved forced dates
  are worse); the gap is watchfulness, not dates.
- `stale` works fine for anything that ever *starts*; PIC-less tasks are already assignable via
  the normal lanes once surfaced.

## Gap

### G56 — Dateless & idle work is invisible to every lamp (severity: MEDIUM)
- **Fix:**
  - New lamp: **`idle`** — status `todo`, no event of any kind for N days (default 14),
    regardless of dates. Radar nudges PICs (or the team lead when PIC-less, which is the
    common case for zombies); digest lists idle tasks in a needs-attention line ("💤 chưa
    khởi động: giáo án nâng cao — 6 tuần, chưa có PIC").
  - **Anchor the end-date warnings:** unconfirmed `end_date_defaulted` tasks and dateless
    campaign tasks get a digest needs-attention line + one radar nudge to the task's lead per
    cadence rules (never per-day nagging). Confirming remains one decision.

## Verdict

**Gap found (G56).** Small and cheap — one lamp and one digest line — but it restores the
review's explicit warning requirement, which rev 7's (correct) de-clocking of programs had
quietly orphaned.

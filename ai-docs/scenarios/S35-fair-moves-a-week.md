# S35 — The fair moves to August 9 (run 7b, vs rev 7)

> Hunt target: **rescheduling the campaign itself.** Event dates move constantly in the real
> world (weather, permits, venues). The project's `end_date` drives defaulting, countdown
> lamps, and close-out — what happens when it changes? Complexity ★★★★.

## Scenario

07-20, permit still pending (TB1). In the Fair events group, linh: "chốt dời fair sang 09/08
nhé — giấy phép chắc chắn không kịp 02/08." At that moment the Fair campaign has: 12 tasks with
explicit end dates ≤ 08-02, 5 tasks on `end_date_defaulted = 08-01` (2 confirmed by leads, 3
never confirmed), and dependency chains tuned to fair week.

## Trace against rev 7

1. **What decision is this?** It changes `projects.end_date` — a real column driving
   defaulting and close-out. The facet registry covers task facets and scope policies
   (`attr:<topic>`); G26 gave project-scoped decisions for *policies*. But `end_date` on the
   project is **not in the registry** — there is no defined op for the single most consequential
   date in a campaign. Extraction would shoehorn it into `attr:end-date` (a policy string with
   no mechanical effect) — recorded, cited… and the system's clock still says 08-02.
2. **Suppose the column changes anyway (dashboard config?):** then the cascade is undefined:
   - The 3 **unconfirmed defaulted** tasks still say 08-01 — stale derivatives of a dead date.
     Should follow to 08-08 (they were never human-confirmed; they exist only as `project.end −
     1`).
   - The 2 **confirmed** defaults and 12 explicit dates must NOT silently move — humans chose
     them — but several now sit oddly early; nothing prompts review.
   - `task.end > project.end` warnings recompute trivially ✓ (rule exists), slack lamps
     recompute ✓ (derived) — the *derived* layer is fine; the *defaulted* layer has no rule.
   - **Close-out arming:** had the date already passed (moving 08-02 → 08-09 *after* 08-02,
     entirely plausible), the project would be `closing` with a close-out sweep already posted
     — and no rule un-arms it.
3. **Authority:** campaign end date should be coordinator-grade (it was set in the all-hands,
   TD1) — currently inexpressible, so unenforceable.

## What holds up ✅

Derived recomputation (warnings, slack, countdown-style lamps) needs zero new rules — the
projection design pays off. Citations/receipts for the reschedule work like any decision. And
the review's own rule ("cần cảnh báo nếu… end date task > end date project") fires correctly
the moment the column moves — for the *inverse* case (project moved earlier), it's the safety
net.

## Gap

### G57 — Project `end_date` is not a decidable facet, and defaulted dates don't cascade
### (severity: MEDIUM-HIGH — rescheduling is routine reality)
- **Fix:**
  - Facet registry gains **project scope, facet `end_date` (set)** — authority: coordinator
    (or all-leads approval); normal lifecycle (supersedes the prior date decision, citable,
    revertible via G17).
  - **Cascade, in the same transaction:** unconfirmed `end_date_defaulted` tasks re-default to
    the new `end − 1` (staying flagged); confirmed/explicit dates untouched, but tasks whose
    dates now violate `task.end > project.end` (or sit > K days before the new end) surface in
    a one-time "reschedule review" list posted to each team (a checklist of proposals, like
    close-out — reusing that machinery).
  - **Closing re-evaluation:** date-triggered `closing` re-arms/disarms when the date moves
    (an explicit coordinator-decided closing sticks regardless).

## Verdict

**Gap found (G57).** The design could *record* "we moved the fair" but not *mean* it. One
facet-registry row plus a cascade rule — and the reschedule-review checklist falls out of
machinery close-out already owns.

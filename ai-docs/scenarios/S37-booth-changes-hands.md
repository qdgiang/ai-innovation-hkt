# S37 — The booth changes hands: moving a task between projects (run 7d, vs rev 7)

> Hunt target: **mid-flight cross-project transfer.** Close-out transfers tasks (campaign →
> program) as a special flow; real orgs also move work between projects while both are alive.
> One-group-one-project makes this *more* common, not less. Complexity ★★★★.

## Scenario

The "kids' demo booth" task lives in the Fair campaign (events team, PIC khoa) with an edge
from the Classes program's "Scratch cohort" task (S30's allowed campaign↔program edge). Mid-July
linh and mai agree in the all-hands group: "booth để bên lớp học lo trọn gói luôn — chuyển
sang Weekend Classes." The booth also has: a dependency **to** another Fair task ("stage
schedule" blocks the booth's slot), events-team ownership, and one pending proposal (decorations).

## Trace against rev 7

1. **What op is this?** The facet registry has `assignment`, `team`, `dependency`, dates,
   `merge`… but **no `project` facet**. A task's project is unrepresentable as a decision —
   the model literally cannot say the one sentence linh just said. (Close-out's transfer is a
   sweep-special-case, not an op.)
2. Suppose forced through as config: the wreckage is instructive —
   - **Team links dangle:** `task_teams` points at *Fair.events*; teams are per-project, so in
     Classes that row is foreign. Must be cleared/remapped; nothing says so.
   - **Dependency edges change legality:** the Scratch→booth edge (campaign↔program ✓) becomes
     *same-project* ✓ — fine. But "stage schedule → booth" was same-project ✓ and becomes
     **campaign↔program in the wrong direction**… which the G51 matrix *allows* (campaign↔
     program ✓ both ways) — OK here, but a transfer to a *different campaign* would create
     forbidden edges; no re-validation step exists anywhere.
   - **The pending decorations proposal** targets the task in its old home; G52 revalidation
     checks canceled/merged — not *moved*. Approving it would write ops under the old project's
     authority assumptions (events lead) though the task now answers to Classes (mai).
   - **Authority for the move itself:** who may transfer? Source lead? Destination lead? Both?
     Undefined.
3. **Defaulting flips:** in Fair the booth had a defaulted end (08-01); in the Classes program
   defaulting doesn't apply — carried date stays but its flag/meaning must re-evaluate.

## What holds up ✅

G51's matrix already answers *which* resulting edges are legal — it just needs to be *consulted*
at transfer time. G52's revalidation pattern extends naturally (moved = one more staleness
condition). Digest/radar homes follow the task's team/project automatically once links are
remapped — no new reporting rules needed.

## Gap

### G59 — No cross-project transfer op (severity: MEDIUM)
- **Fix:** facet registry gains **`project` (set)** on tasks:
  - **Authority: two-key** — source project's lead + destination project's lead (either may
    propose; the other's approval makes it effective; coordinator alone also suffices). Matches
    the delegation/approval machinery as-is.
  - **Transfer transaction:** re-validate every edge against the G51 matrix under the new
    homes (violations → edge flagged `needs-rewire`, both PICs notified); clear `task_teams`
    (destination lead re-teams, or the task rides as project-level per G48); re-evaluate
    dating under the destination (program → drop the defaulted flag; campaign → default+flag
    if dateless); **pending proposals on the task are put `pending-revalidation`** — approvers
    see "task moved to Weekend Classes (mai)" and the approval re-routes to the new home's
    authority (G52's card-shows-current-state rule extended with *moved*).
  - History is untouched: prior decisions keep their citations and their old-project context
    in the popup ("decided while in Charity Fair 2026").

## Verdict

**Gap found (G59).** One-group-one-project (settled #13) made project boundaries hard walls —
which is exactly why work needs a *door*: an explicit, two-key, edge-revalidating transfer op.
All of its parts reuse existing machinery.

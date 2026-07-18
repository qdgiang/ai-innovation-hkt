# EVM-014 — Decide how task split is represented

> Priority: P1 · Status: `OPEN`

## Problem

Rev 9 says split is composed from child creation and parent refinement, while UI scenarios offer a
one-tap split. No relation currently tells projections or reasoning views which children belong to
the split.

## Options

- **Option A — Generic task-relation graph:** flexible but speculative for one decomposition use case.
- **Option B — Nullable `parent_task_id`:** smallest honest representation if split remains in MVP.
- **Option C — Defer one-tap split (`PROPOSED` when not required by the hero demo):** allow manual child
  tasks and avoid promising a flow the model cannot explain.

## Acceptance criteria

- MVP explicitly chooses B or C; it does not claim split without a representation.
- If B is chosen, child creation and parent linkage are atomic/auditable.
- Parent status is not silently derived from children without a separate approved rule.
- Merge and transfer preserve or deliberately revalidate parent linkage.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — Option C for the flow, Option B's column for the record.** The MVP makes no
one-tap-split promise: split remains what rev 13 says it is — compose (create children +
refine the parent), each step an ordinary decision. Adopted from Option B (rev-14 queue): a
nullable `tasks.parent_task_id`, stamped when the compose flow creates a child, so lineage is
renderable in the popup instead of only reconstructable from decision history. Explicit
non-rules, per the criteria: parent status is **never** derived from children (no roll-up rule
exists unless separately approved); the contested-lamp suggestion (G55) posts ordinary
child-task *proposals*, not a split op. Merge/transfer handling: transfer re-validates the
parent link like any edge (`pending-revalidation`, G59); merging a child re-points its parent
link to nothing — the survivor's history carries the story.

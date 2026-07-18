"""Owner: B. TSK-4 — merge (G43/G60). Split is deliberately NOT a function
here: design-v2.md is explicit that "split = compose (create children +
refine parent), not a new op" — it's just ordinary `description`/
`parent_task_id` facet ops through the normal fold (see `fold.py`'s
`TASK_FIELD_FACETS`), so there's nothing merge-shaped to write for it.
"""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from evermind.contracts.enums import TaskStatus
from evermind.tasks import dependencies
from evermind.tasks.dependencies import DependencyCycleError
from evermind.tasks.models import (
    Task, TaskAssignment, TaskDecisionLog, TaskDependency, TaskTeam, TaskUpdate,
)


def merge_tasks(session: Session, *, absorbed_id: int, survivor_id: int) -> None:
    """Re-points everything from `absorbed` onto `survivor`, unions
    assignments/teams, drops the pair-internal edge (identity confusion, not
    sequencing — G43), re-points the rest, then re-checks the DAG over the
    survivor (G60) — a cycle raises `DependencyCycleError` and the caller's
    transaction must roll back (this function doesn't reverse its own writes).
    """
    absorbed = session.get(Task, absorbed_id)
    survivor = session.get(Task, survivor_id)
    if absorbed is None or survivor is None:
        raise LookupError("both tasks must exist to merge")

    _union_slot_table(session, TaskAssignment, "user_id", absorbed_id, survivor_id)
    _union_slot_table(session, TaskTeam, "team_id", absorbed_id, survivor_id)

    session.execute(
        update(TaskUpdate)
        .where(TaskUpdate.task_id == absorbed_id)
        .values(task_id=survivor_id)
    )
    session.execute(
        update(TaskDecisionLog)
        .where(TaskDecisionLog.task_id == absorbed_id)
        .values(task_id=survivor_id)
    )

    # drop the pair-internal edge in either direction (G43 — identity
    # confusion between the two merging tasks, not real sequencing)
    session.execute(
        delete(TaskDependency).where(
            ((TaskDependency.predecessor_task_id == absorbed_id)
             & (TaskDependency.successor_task_id == survivor_id))
            | ((TaskDependency.predecessor_task_id == survivor_id)
               & (TaskDependency.successor_task_id == absorbed_id))
        )
    )

    _redirect_edges(session, absorbed_id, survivor_id)

    absorbed.status = TaskStatus.MERGED
    absorbed.merged_into = survivor_id

    # the session uses autoflush=False (db/session.py) — the cycle check
    # below queries via fresh SELECTs, so the redirects above must be
    # flushed first or it would see stale (pre-merge) edges.
    session.flush()
    if dependencies.has_cycle_through(session, survivor_id):
        raise DependencyCycleError([survivor_id])


def _union_slot_table(session: Session, model, slot_field: str,
                       absorbed_id: int, survivor_id: int) -> None:
    rows = session.scalars(select(model).where(model.task_id == absorbed_id)).all()
    for row in rows:
        slot_value = getattr(row, slot_field)
        exists = session.get(model, {"task_id": survivor_id, slot_field: slot_value})
        if exists is None:
            session.add(model(task_id=survivor_id, **{slot_field: slot_value}))
        session.delete(row)


def _redirect_edges(session: Session, absorbed_id: int, survivor_id: int) -> None:
    as_predecessor = session.scalars(
        select(TaskDependency).where(TaskDependency.predecessor_task_id == absorbed_id)
    ).all()
    for edge in as_predecessor:
        existing = session.get(TaskDependency, {
            "predecessor_task_id": survivor_id, "successor_task_id": edge.successor_task_id,
        })
        if existing is not None:
            session.delete(edge)
        else:
            edge.predecessor_task_id = survivor_id

    as_successor = session.scalars(
        select(TaskDependency).where(TaskDependency.successor_task_id == absorbed_id)
    ).all()
    for edge in as_successor:
        existing = session.get(TaskDependency, {
            "predecessor_task_id": edge.predecessor_task_id, "successor_task_id": survivor_id,
        })
        if existing is not None:
            session.delete(edge)
        else:
            edge.successor_task_id = survivor_id

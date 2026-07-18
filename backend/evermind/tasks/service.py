"""Owner: B. Read port for the `tasks` fold — consumed by `signals`, `surfacing`,
`decisions` (interface #9: task-state read port, read-only), and the API routers.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.tasks.fold import TASK_FIELD_FACETS
from evermind.tasks.models import (
    Task, TaskAssignment, TaskDecisionLog, TaskDependency, TaskUpdate,
)


class TasksService:
    def __init__(self, session: Session):
        self.session = session

    def get_task(self, task_id: int) -> Task | None:
        return self.session.get(Task, task_id)

    def dependencies_of(self, task_id: int) -> list[TaskDependency]:
        """TSK-3 — predecessor/successor edges for radar + dependency lamps."""
        return list(
            self.session.scalars(
                select(TaskDependency).where(
                    (TaskDependency.predecessor_task_id == task_id)
                    | (TaskDependency.successor_task_id == task_id)
                )
            )
        )

    def is_pic(self, task_id: int, user_id: int) -> bool:
        """TSK-2 — the single fact `decisions.service` needs to route an update
        lane (G7 auto-apply vs G9 confirm-card); the rank/authority half of that
        decision is `decisions`' own job, not read from here.
        """
        return (
            self.session.get(TaskAssignment, {"task_id": task_id, "user_id": user_id})
            is not None
        )

    def is_terminal(self, task_id: int) -> bool:
        """TSK-6 — canceled/merged tasks lock the update lanes to notes only."""
        task = self.session.get(Task, task_id)
        return task is not None and task.status in ("canceled", "merged")

    def merged_survivor(self, task_id: int) -> int | None:
        """TSK-6 — ops aimed at a merged husk auto-redirect to the survivor."""
        task = self.session.get(Task, task_id)
        return task.merged_into if task is not None else None

    def at(self, task_id: int, ts: datetime) -> dict:
        """TSK-8 time-travel — reconstruct task state at `ts` by replaying this
        task's `TaskDecisionLog` + status-kind `TaskUpdate` rows up to `ts`, in
        event-time order. Powers `GET /tasks/{id}/at` and the reasoning popup
        (S15). Does not touch the live `Task` row.
        """
        state: dict = {
            "description": None, "status": "todo", "start_date": None, "end_date": None,
            "end_date_defaulted": False, "kind": None, "type": "undefined", "note": None,
            "assignments": set(), "teams": set(),
        }

        decision_rows = self.session.scalars(
            select(TaskDecisionLog)
            .where(TaskDecisionLog.task_id == task_id)
            .where(TaskDecisionLog.ts <= ts)
            .where(TaskDecisionLog.retracted.is_(False))
        ).all()
        update_rows = self.session.scalars(
            select(TaskUpdate)
            .where(TaskUpdate.task_id == task_id)
            .where(TaskUpdate.ts <= ts)
            .where(TaskUpdate.kind == "status")
        ).all()

        events: list[tuple[datetime, datetime, str, Any]] = [
            (row.ts, row.recorded_at, "decision", row) for row in decision_rows
        ] + [
            (row.ts, row.recorded_at, "update", row) for row in update_rows
        ]
        events.sort(key=lambda e: (e[0], e[1]))

        target_prefix = f"task:{task_id}"
        for _, _, kind, row in events:
            if kind == "decision":
                for op in row.ops:
                    if op["target"] != target_prefix:
                        continue  # multi-op decision touching other tasks too
                    _apply_op_to_state(state, op)
            else:  # kind == "update" — G7 PIC auto-apply, never supersedes
                state["status"] = row.payload["status"]

        return state


def _apply_op_to_state(state: dict, op: dict) -> None:
    facet, verb, value = op["facet"], op["op"], op.get("value")
    if facet in TASK_FIELD_FACETS:
        state[facet] = value
    elif facet == "assignment":
        _apply_slot_op_to_state(state, "assignments", verb, value)
    elif facet == "team":
        _apply_slot_op_to_state(state, "teams", verb, value)
    elif facet == "note":
        state["note"] = f"{state['note']}\n{value}" if state["note"] else str(value)
    # dependency/attr:* ops don't affect single-task field state


def _apply_slot_op_to_state(state: dict, key: str, verb: str, value) -> None:
    if verb == "add":
        state[key].add(value)
    elif verb == "remove":
        state[key].discard(value)
    elif verb == "set":
        state[key] = set(value)

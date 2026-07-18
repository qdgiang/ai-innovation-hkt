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
    Task, TaskAssignment, TaskDecisionLog, TaskDependency, TaskTeam, TaskUpdate,
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

    def list_tasks(self, *, project_id: int | None = None,
                    statuses: tuple[str, ...] | None = None,
                    team_id: int | None = None, pic_user_id: int | None = None,
                    description_contains: str | None = None) -> list[Task]:
        """Read port for SIG-3 radar + SRF-3 digest + DSH-4's task board filter
        matrix — every task, optionally scoped by project/status/team/PIC/text.
        """
        stmt = select(Task)
        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        if statuses is not None:
            stmt = stmt.where(Task.status.in_(statuses))
        if team_id is not None:
            stmt = stmt.where(Task.id.in_(
                select(TaskTeam.task_id).where(TaskTeam.team_id == team_id)
            ))
        if pic_user_id is not None:
            stmt = stmt.where(Task.id.in_(
                select(TaskAssignment.task_id).where(TaskAssignment.user_id == pic_user_id)
            ))
        if description_contains is not None:
            stmt = stmt.where(Task.description.ilike(f"%{description_contains}%"))
        return list(self.session.scalars(stmt))

    def reasoning_log(self, task_id: int) -> dict:
        """Popup log — dual stamps (ts vs recorded_at) for everything this
        module tracks (design-v2.md §Reasoning views, the tasks-owned half).
        Citation badges + show-inactive (superseded/rejected decisions) need
        `decisions` (Lane A, not built) — TODO once it exists.
        """
        decision_rows = self.session.scalars(
            select(TaskDecisionLog)
            .where(TaskDecisionLog.task_id == task_id)
            .order_by(TaskDecisionLog.ts)
        ).all()
        update_rows = self.session.scalars(
            select(TaskUpdate).where(TaskUpdate.task_id == task_id).order_by(TaskUpdate.ts)
        ).all()

        log = [
            {"source": "decision", "decision_id": row.decision_id, "ts": row.ts,
             "recorded_at": row.recorded_at, "ops": row.ops, "retracted": row.retracted}
            for row in decision_rows
        ] + [
            {"source": "update", "ts": row.ts, "recorded_at": row.recorded_at,
             "actor_user_id": row.actor_user_id, "kind": row.kind, "payload": row.payload}
            for row in update_rows
        ]
        log.sort(key=lambda entry: (entry["ts"], entry["recorded_at"]))
        return {"task": self.get_task(task_id), "log": log}

    def pics_of(self, task_id: int) -> list[int]:
        """G1: a task may have several PICs (multi-slot assignment)."""
        return list(
            self.session.scalars(
                select(TaskAssignment.user_id).where(TaskAssignment.task_id == task_id)
            )
        )

    def last_event_at(self, task_id: int) -> datetime | None:
        """Latest of any `task_updates` row or `task_decision_log` row touching
        this task — the "no event of any kind" clock SIG-3's stale/idle lamps
        need (G56/G8: in-doing no event N days / todo no event 14 days).
        """
        update_ts = self.session.scalar(
            select(TaskUpdate.ts).where(TaskUpdate.task_id == task_id)
            .order_by(TaskUpdate.ts.desc()).limit(1)
        )
        decision_ts = self.session.scalar(
            select(TaskDecisionLog.ts).where(TaskDecisionLog.task_id == task_id)
            .where(TaskDecisionLog.retracted.is_(False))
            .order_by(TaskDecisionLog.ts.desc()).limit(1)
        )
        candidates = [ts for ts in (update_ts, decision_ts) if ts is not None]
        return max(candidates) if candidates else None

    def status_flip_actors(self, task_id: int, *, since: datetime) -> list[tuple[datetime, int]]:
        """G55 contested lamp input: (ts, actor_user_id) for every status-kind
        update since `since`."""
        rows = self.session.execute(
            select(TaskUpdate.ts, TaskUpdate.actor_user_id)
            .where(TaskUpdate.task_id == task_id)
            .where(TaskUpdate.kind == "status")
            .where(TaskUpdate.ts >= since)
            .order_by(TaskUpdate.ts)
        ).all()
        return [(row.ts, row.actor_user_id) for row in rows]

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
    if facet == "end_date":
        # mirrors fold.apply_op's TSK-7 handling — see its comment
        if isinstance(value, dict):
            state["end_date"] = value["value"]
            state["end_date_defaulted"] = bool(value.get("end_date_defaulted", False))
        else:
            state["end_date"] = value
            state["end_date_defaulted"] = False
    elif facet in TASK_FIELD_FACETS:
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

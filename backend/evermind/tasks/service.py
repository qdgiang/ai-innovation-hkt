"""Owner: B. Read port for the `tasks` fold — consumed by `signals`, `surfacing`,
`decisions` (interface #9: task-state read port, read-only), and the API routers.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from evermind.tasks.models import Task, TaskDependency


class TasksService:
    def __init__(self, session: Session):
        self.session = session

    def get_task(self, task_id: int) -> Task | None:
        return self.session.get(Task, task_id)

    def dependencies_of(self, task_id: int) -> list[TaskDependency]:
        """TODO(B): TSK-3 — predecessor/successor edges for radar + dependency lamps."""
        raise NotImplementedError

    def at(self, task_id: int, ts: datetime) -> dict:
        """TODO(B): TSK-8 time-travel — reconstruct task state at `ts` by replaying
        this task's decisions/updates up to that event time. Powers
        `GET /tasks/{id}/at` and the reasoning popup (S15).
        """
        raise NotImplementedError

    def route_update_lane(self, task_id: int, actor_user_id: int) -> str:
        """TODO(B): TSK-2 — "is the cited author a PIC?" (PIC auto-apply vs authority
        vs confirm-card). Read via this module's own projection; `decisions.service`
        calls this during RecordTaskUpdate routing (interface #9).
        """
        raise NotImplementedError

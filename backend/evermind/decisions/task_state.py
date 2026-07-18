"""A-owned structural port for B's read-only task projection (interface #9)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from evermind.contracts.enums import TaskStatus


@dataclass(frozen=True)
class TaskStateView:
    id: int
    project_id: int
    status: TaskStatus
    pic_user_ids: frozenset[int]
    owning_team_ids: frozenset[int]
    merged_into: int | None
    current_version: str

    def is_pic(self, user_id: int) -> bool:
        return user_id in self.pic_user_ids

    @property
    def terminal(self) -> bool:
        return self.status in {TaskStatus.CANCELED, TaskStatus.MERGED}

    @property
    def merged_survivor(self) -> int | None:
        return self.merged_into if self.status is TaskStatus.MERGED else None


class TaskStatePort(Protocol):
    def get_task(self, task_id: int) -> TaskStateView | None: ...


class NullTaskStatePort:
    """Fail-closed default until B's projection adapter is injected."""

    def get_task(self, task_id: int) -> TaskStateView | None:
        return None

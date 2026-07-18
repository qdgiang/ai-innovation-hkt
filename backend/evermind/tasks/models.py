"""Owner: B. THE FOLD — tasks + derived joins, task_updates, task_dependencies
(data-model.md §Task projection). DERIVED — never hand-edited; only written by
this module's event consumer (`tasks/consumer.py`), never by raw commands.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from evermind.contracts.enums import DependencyStatus, TaskKind, TaskStatus, TaskType
from evermind.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    kind: Mapped[TaskKind]  # ongoing = recurring/program work, exempt from end-date defaulting
    type: Mapped[TaskType] = mapped_column(default=TaskType.UNDEFINED)
    description: Mapped[str]
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.TODO)
    merged_into: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))  # [EVM-014]
    # parent status NEVER derived from children
    start_date: Mapped[datetime | None]
    end_date: Mapped[datetime | None]
    end_date_defaulted: Mapped[bool] = mapped_column(default=False)
    blocked_waiting_on_party_id: Mapped[int | None]
    blocked_waiting_on_text: Mapped[str | None]
    blocked_since: Mapped[datetime | None]
    note: Mapped[str | None]


class TaskAssignment(Base):
    """DERIVED (per-person-slot ops, G1 — multi-PIC supported)."""

    __tablename__ = "task_assignments"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)


class TaskTeam(Base):
    """DERIVED."""

    __tablename__ = "task_teams"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(primary_key=True)


class TaskUpdate(Base):
    """The PIC progress lane (G7); NOT a decision; never supersedes anything."""

    __tablename__ = "task_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime]
    recorded_at: Mapped[datetime]
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    actor_user_id: Mapped[int]
    kind: Mapped[str]  # status | note
    payload: Mapped[dict]
    created_from: Mapped[str]
    confidence: Mapped[float | None]
    source_message_id: Mapped[int | None]


class TaskDependency(Base):
    """Blocks-only DAG (cycle check at write); only `confirmed` derives lamps.
    Admission matrix = G51 (enforced in service, not schema).
    """

    __tablename__ = "task_dependencies"

    predecessor_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    successor_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    created_by_decision_id: Mapped[int]
    status: Mapped[DependencyStatus] = mapped_column(default=DependencyStatus.REQUESTED)

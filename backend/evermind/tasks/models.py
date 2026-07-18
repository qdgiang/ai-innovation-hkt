"""Owner: B. THE FOLD — tasks + derived joins, task_updates, task_dependencies
(data-model.md §Task projection). DERIVED — never hand-edited; only written by
this module's event consumer (`tasks/consumer.py`), never by raw commands.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from evermind.contracts.enums import (
    DependencyStatus, ProjectKind, TaskKind, TaskStatus, TaskType,
)
from evermind.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    # Denormalized from `org` at task-creation time (by decisions.service, which
    # may read org) — NOT a live join. architecture.md forbids `tasks` importing
    # `org`, but TSK-3's G51 admission matrix needs a project's campaign/program
    # kind to decide cross-project dependency edges; carrying it here avoids the
    # import. Refresh it if a project's kind is ever allowed to change (design-
    # v2 currently treats [D4] `projects.kind` as immutable post-creation).
    project_kind: Mapped[ProjectKind] = mapped_column(default=ProjectKind.PROGRAM)
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
    payload: Mapped[dict] = mapped_column(JSON)
    created_from: Mapped[str]
    confidence: Mapped[float | None]
    source_message_id: Mapped[int | None]


class TaskDecisionLog(Base):
    """OWNED BY `tasks` — a private replay log, NOT a copy of `decisions`.

    architecture.md says "`tasks` imports nothing but `contracts`", so TSK-8
    time-travel cannot re-read the `decisions` table. Instead, every
    `decision_effective` domain event this module consumes is also appended
    here (task_id, decision_ts, the ops that applied). `TasksService.at()`
    replays rows with `ts <= given ts` through the same fold logic used for
    the live projection — last-write-wins per facet naturally reproduces "what
    was effective at that time" (data-model.md invariant #5: ordering is
    `(ts, recorded_at, stable_event_id)`).
    """

    __tablename__ = "task_decision_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    decision_id: Mapped[int]
    ts: Mapped[datetime]
    recorded_at: Mapped[datetime]
    stable_event_id: Mapped[str | None]
    ops: Mapped[list[dict]] = mapped_column(JSON)
    retracted: Mapped[bool] = mapped_column(default=False)
    # True when the decision was later rejected (e.g. veto of a once-effective
    # decision, DEC-6) — excluded from replay. A known simplification: this
    # flips the row out of ALL future replays rather than only ts-after-the-
    # rejection ones (the recorded_at-vs-ts dual-stamp nuance — revisit before
    # the G17 resurrection scenario needs it precisely).


class TaskDependency(Base):
    """Blocks-only DAG (cycle check at write); only `confirmed` derives lamps.
    Admission matrix = G51 (enforced in service, not schema).
    """

    __tablename__ = "task_dependencies"

    predecessor_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    successor_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    created_by_decision_id: Mapped[int]
    status: Mapped[DependencyStatus] = mapped_column(default=DependencyStatus.REQUESTED)

"""Owner: A. THE CORE — decisions, citations, proposal state, acts, the universal
command gateway's plumbing (`processed_commands`, `domain_events`, `projection_offsets`).
data-model.md §Decisions + §Write-path plumbing.

`tasks`/`signals`/`surfacing` (B) never write these tables — they consume
`domain_events` via their own `projection_offsets` row (architecture.md import rule:
"decisions imports nothing but contracts + org (read-only)").
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from evermind.contracts.enums import (
    ApprovalVia, CitationKind, CreatedFrom, DecisionScope, DecisionStatus, RejectedReason,
)
from evermind.db.base import Base


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime]  # event time — fold/supersession direction (G31)
    recorded_at: Mapped[datetime]  # ingestion time
    decided_by_user_id: Mapped[int]
    decided_by_role_at_time: Mapped[int]  # rank SNAPSHOT (G10 gate)
    scope: Mapped[DecisionScope]
    scope_target: Mapped[str]
    description: Mapped[str]
    context: Mapped[str | None]
    note: Mapped[str | None]
    ops: Mapped[list[dict]] = mapped_column(JSON)  # [{target, facet, op, value}]
    effect_window_from: Mapped[datetime | None]
    effect_window_until: Mapped[datetime | None]  # G42 — shadows, never supersedes
    status: Mapped[DecisionStatus] = mapped_column(default=DecisionStatus.PROPOSED)
    rejected_reason: Mapped[RejectedReason | None]
    supersedes_decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"))
    superseded_by_decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"))
    approved_by_user_id: Mapped[int | None]
    approval_via: Mapped[ApprovalVia | None]
    approved_by_role_at_act: Mapped[int | None]  # [EVM-005] snapshot at act time
    created_from: Mapped[CreatedFrom]
    confidence: Mapped[float | None]
    window_id: Mapped[int | None]
    stable_event_id: Mapped[str | None]  # [EVM-012] ordering tiebreak
    # Task-creation context, stamped at propose time for NEW_TASK decisions so
    # the APPROVAL path can emit the same new_task_id/project_id the
    # born-effective path does — without it the consumer materializes the task
    # under the 0-placeholder project (PR #42 review gap).
    new_task_id: Mapped[int | None]
    context_project_id: Mapped[int | None]

    # Append-only enforcement (settled #2): a DB trigger rejects UPDATEs on body
    # columns (ts, decided_by_*, scope*, description, context, ops, effect_window,
    # created_from, confidence). Add the trigger in the migration, not here.


class DecisionTask(Base):
    __tablename__ = "decision_tasks"

    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), primary_key=True)
    task_id: Mapped[int] = mapped_column(primary_key=True)  # FK to tasks.tasks — cross-module,
    # enforced at the application layer only (tasks table is owned by module `tasks`)


class DecisionCitation(Base):
    __tablename__ = "decision_citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    message_id: Mapped[int]  # FK to connectors.messages — cross-module, app-layer enforced
    kind: Mapped[CitationKind]
    rev_at_capture: Mapped[int]
    rev_at_act: Mapped[int | None]  # approval rows only (G65)


class EffectiveUnit(Base):
    """One-effective-per-unit index (data-model.md invariant #2): maintained inside
    the effective-write transaction, not derivable from a partial index on JSONB.
    """

    __tablename__ = "effective_units"

    unit_key: Mapped[str] = mapped_column(primary_key=True)
    # NOT unique: a multi-op decision occupies several units at once [EVM-003];
    # uniqueness-per-unit is the PK
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), index=True)


class DecisionUnit(Base):
    """Every unit a decision's ops touch, proposed or effective (decisions-
    internal index; added in migration 0002). `effective_units` answers "who
    occupies this unit"; this table answers "which decisions touch it" — the
    sweep (G11/G12), pending-merge (G49), change-of-mind withdrawal (#17b), and
    effect-window overlap checks [EVM-004] all query it.
    """

    __tablename__ = "decision_units"

    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), primary_key=True)
    unit_key: Mapped[str] = mapped_column(primary_key=True)


class IdAllocation(Base):
    """Task-id allocator for NEW_TASK decisions (migration 0002). The tasks
    table is B's projection — its rows are *created by the fold* from
    decision_effective events, so the task identity must be minted on the write
    side (here) and carried in the event payload.
    """

    __tablename__ = "id_allocations"

    name: Mapped[str] = mapped_column(primary_key=True)
    next_id: Mapped[int] = mapped_column(default=1)


class ProcessedCommand(Base):
    """[EVM-021] dashboard/API idempotency: retries return the recorded outcome."""

    __tablename__ = "processed_commands"

    client_command_id: Mapped[str] = mapped_column(primary_key=True)
    persona: Mapped[str]
    received_at: Mapped[datetime]
    outcome: Mapped[dict] = mapped_column(JSON)


# NOTE: `DomainEvent` / `ProjectionOffset` live in `evermind.db.eventlog`, not here —
# `tasks`/`signals`/`surfacing` (B) must read the event log without importing this
# module (architecture.md: "tasks imports nothing but contracts"). `decisions.service`
# (A) still owns the WRITE side (appends events transactionally); it imports
# `db.eventlog` like everyone else.

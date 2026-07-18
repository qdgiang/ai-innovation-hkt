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
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), unique=True)


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

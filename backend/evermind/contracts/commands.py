"""Command union — the only way anything writes to the domain core.

architecture.md §The write pipeline: every surface (chat reply/react, marker,
LLM extraction, dashboard tap) becomes one of these and enters through
`decisions.service` (owned by A). `tasks`/`signals`/`surfacing` (owned by B)
NEVER construct domain writes directly — they emit these commands and consume
`domain_events` back.

Frozen for the phase after P1's contract-first PR (plan.md). Changing a command
shape mid-phase is a `contract-change` PR, both lanes sign off.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionScope


class CommandEnvelope(BaseModel):
    """Common fields every command carries — provenance + idempotency [EVM-021]."""

    client_command_id: UUID
    persona: str  # persona_user_id asserted by the caller; api does scoping only
    expected_version: str | None = None  # current same-unit decision id / task event id
    created_from: CreatedFrom
    source_message_id: int | None = None
    window_id: int | None = None
    confidence: float | None = None


class OpSpec(BaseModel):
    """One facet op inside a decision (data-model.md §Decisions, `ops JSONB`)."""

    target: str  # e.g. "task:42", "team:5", "project:3"
    facet: str  # facet-registry key, e.g. "assignment:add", "attr:venue"
    op: str
    value: Any


class CitationSpec(BaseModel):
    message_id: int
    kind: CitationKind
    rev_at_capture: int
    rev_at_act: int | None = None


class ProposeDecision(CommandEnvelope):
    kind: Literal["propose_decision"] = "propose_decision"
    decided_by_user_id: int
    scope: DecisionScope
    scope_target: str
    description: str
    context: str | None = None
    ops: list[OpSpec]
    effect_window: tuple[datetime, datetime] | None = None
    citations: list[CitationSpec]


class ApproveProposal(CommandEnvelope):
    kind: Literal["approve_proposal"] = "approve_proposal"
    decision_id: int
    approved_by_user_id: int
    rev_at_act: int | None = None


class RejectProposal(CommandEnvelope):
    kind: Literal["reject_proposal"] = "reject_proposal"
    decision_id: int
    rejected_by_user_id: int
    reason: Literal["veto", "dismissed"]


class RecordTaskUpdate(CommandEnvelope):
    """Owned by B (`tasks`) but STILL enters via `decisions.service` — the gateway
    routes PIC-auto vs authority vs confirm-card (architecture.md line 177-181).
    """

    kind: Literal["record_task_update"] = "record_task_update"
    task_id: int
    actor_user_id: int
    update_kind: Literal["status", "note"]
    payload: dict[str, Any]


class RecordSignal(CommandEnvelope):
    """Owned by B (`signals`) — same gateway rule as RecordTaskUpdate."""

    kind: Literal["record_signal"] = "record_signal"
    signal_kind: Literal["blocker", "dependency", "ask", "parked"]
    project_id: int
    task_id: int | None = None
    party_id: int | None = None
    normalized_topic: str
    excerpt: str


class AppendCorroboration(CommandEnvelope):
    kind: Literal["append_corroboration"] = "append_corroboration"
    decision_id: int
    citation: CitationSpec


class RegisterReactionAct(CommandEnvelope):
    kind: Literal["register_reaction_act"] = "register_reaction_act"
    message_id: int
    user_id: int
    emoji: str
    removed: bool = False


Command = (
    ProposeDecision
    | ApproveProposal
    | RejectProposal
    | RecordTaskUpdate
    | RecordSignal
    | AppendCorroboration
    | RegisterReactionAct
)

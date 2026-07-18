"""Owner: A. UI actions leave chat evidence FIRST (phân-quyền spec, settled
in-session 2026-07-19: "UI không âm thầm sửa task").

Every DASHBOARD-born command gets a `messages` row describing the act —
appended to the project's evidence stream and cited/stamped on the command —
BEFORE the gateway applies it, in the same transaction. The row is internal
(`source="dashboard"`): nothing is ever sent to any platform (settled #20
stands — capture is read-only; outbound-to-Telegram is an explicit later
design if ever).

This lives in `api` (the composition root), not `decisions`: the gateway may
not import `connectors` (import contract), and evidence-stream writes are
composition, not domain logic.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message
from evermind.contracts.commands import (
    ApproveProposal, BulkProposalAction, CitationSpec, Command, ProposeDecision,
    RecordTaskUpdate, RejectProposal,
)
from evermind.contracts.enums import CitationKind
from evermind.decisions.models import DecisionCitation
from evermind.org.models import ChatGroup
from evermind.tasks.models import Task

# Disjoint id range: messages.id has per-source numbering schemes (corpus =
# line number, telegram = 2_000_000_000 + hash) — dashboard acts get their own.
_DASHBOARD_ID_BASE = 1_500_000_000


def _render(command: Command) -> str:
    """Human-readable Vietnamese line — this is what the receipt shows."""
    if isinstance(command, ApproveProposal):
        return f"[UI] {command.persona} duyệt đề xuất #{command.decision_id}"
    if isinstance(command, RejectProposal):
        return (f"[UI] {command.persona} từ chối đề xuất "
                f"#{command.decision_id} ({command.reason})")
    if isinstance(command, ProposeDecision):
        return f"[UI] {command.persona} đề xuất: {command.description}"
    if isinstance(command, RecordTaskUpdate):
        return (f"[UI] {command.persona} cập nhật task #{command.task_id}: "
                f"{command.update_kind}={command.payload}")
    if isinstance(command, BulkProposalAction):
        return f"[UI] {command.persona} thao tác hàng loạt: {command.action}"
    return f"[UI] {command.persona}: {command.kind}"


def _resolve_group_id(session: Session, command: Command) -> int | None:
    """Best-effort routing of the act into the project's evidence stream —
    an unroutable act still leaves evidence, just group-less."""
    if isinstance(command, ProposeDecision):
        return command.context_group_id
    if isinstance(command, (ApproveProposal, RejectProposal)):
        cited = session.scalar(
            select(Message.group_id)
            .join(DecisionCitation, DecisionCitation.message_id == Message.id)
            .where(DecisionCitation.decision_id == command.decision_id)
            .limit(1))
        return cited
    if isinstance(command, RecordTaskUpdate):
        project_id = session.scalar(
            select(Task.project_id).where(Task.id == command.task_id))
        if project_id is None:
            return None
        return session.scalar(
            select(ChatGroup.id).where(ChatGroup.project_id == project_id)
            .order_by(ChatGroup.id).limit(1))
    return None


def leave_dashboard_evidence(session: Session, command: Command) -> Command:
    """Append (idempotently) the act's evidence message and return the command
    stamped with it (`source_message_id`; proposals also gain a citation)."""
    raw_ref = f"dashboard:{command.client_command_id}"
    message = session.scalar(select(Message).where(Message.raw_ref == raw_ref))
    if message is None:
        message = Message(
            id=_DASHBOARD_ID_BASE + command.client_command_id.int % 100_000_000,
            source="dashboard",
            group_id=_resolve_group_id(session, command),
            author_identity=command.persona,
            ts=datetime.now(timezone.utc),
            text=_render(command),
            thread_ref=None,
            raw_ref=raw_ref,
            kind="text",
        )
        session.add(message)
        session.flush()

    update: dict = {"source_message_id": message.id}
    if isinstance(command, ProposeDecision):
        update["citations"] = [
            *command.citations,
            CitationSpec(message_id=message.id, kind=CitationKind.EVIDENCE,
                         rev_at_capture=1),
        ]
    return command.model_copy(update=update)

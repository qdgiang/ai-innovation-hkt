"""Command union — the only way anything writes to the domain core.

architecture.md §The write pipeline: every surface (chat reply/react, marker,
LLM extraction, dashboard tap) becomes one of these and enters through
`decisions.service` (owned by A). `tasks`/`signals`/`surfacing` (owned by B)
NEVER construct domain writes directly — they emit these commands and consume
`domain_events` back.

Frozen for the phase after P1's contract-first PR (plan.md). Changing a command
shape mid-phase is a `contract-change` PR, both lanes sign off.

P1 contract-first additions (Lane A, review requested from B):
- `CommandEnvelope.ts` — event time (fold/supersession direction, G31/[EVM-012]);
  None ⇒ the gateway stamps now. `recorded_at` is always gateway-stamped.
- `ProposeDecision.relayed` — set by ingestion when the claimed maker is not
  among the cited authors ("posting for mai") ⇒ born proposed, self-confirm lane.
- `ProposeDecision.delegated_by_user_id` / `.delegation_message_id` — G25:
  an authorized user's cited in-thread message authorizes the maker
  (`approval_via=delegation`, both messages cited).
- `ProposeDecision.context_group_id` — the chat group the content arrived in;
  authority for `NEW_TASK` targets is checked against this group's team (G3).
- `ApproveProposal.ack_revalidation` — G52: the approver saw the diff /
  canceled / merged card and confirms anyway.
- `BulkProposalAction` — DEC-7 approver bulk acts (approve all / dismiss all
  from person / dismiss stale — each an explicit human act, settled #18).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field

from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionScope


class CommandEnvelope(BaseModel):
    """Common fields every command carries — provenance + idempotency [EVM-021]."""

    client_command_id: UUID
    persona: str  # persona_user_id asserted by the caller; api does scoping only
    expected_version: str | None = None  # current same-unit effective decision id
    created_from: CreatedFrom
    ts: datetime | None = None  # EVENT time (G31); None => gateway stamps now
    source_message_id: int | None = None
    window_id: int | None = None
    confidence: float | None = None


class OpSpec(BaseModel):
    """One facet op inside a decision (data-model.md §Decisions, `ops JSONB`).

    `target`: "task:42" | "team:5" | "project:3" | "NEW_TASK" (gateway allocates
    the task id and rewrites the target before the event is appended).
    `facet`: facet-registry key — "status", "assignment", "attr:budget", …
    """

    target: str
    facet: str
    op: str  # set | add | remove | append
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
    note: str | None = None
    ops: list[OpSpec]
    effect_window: tuple[datetime, datetime] | None = None
    citations: list[CitationSpec]
    relayed: bool = False
    delegated_by_user_id: int | None = None
    delegation_message_id: int | None = None
    context_group_id: int | None = None
    # system-initiated proposals (harvested from PR #53, credit pqminh27):
    # `force_proposed` holds the decision as PROPOSED regardless of authority/
    # confidence; `review_reason` says WHY on the inbox card; `reported_by`
    # keeps the human whose evidence triggered it (promotion: first mention).
    force_proposed: bool = False
    review_reason: Literal["signal_promotion"] | None = None
    reported_by_user_id: int | None = None


class ApproveProposal(CommandEnvelope):
    kind: Literal["approve_proposal"] = "approve_proposal"
    decision_id: int
    approved_by_user_id: int
    rev_at_act: int | None = None
    ack_revalidation: bool = False  # G52 diff/canceled/merged card confirmed


class RejectProposal(CommandEnvelope):
    """Veto / dismiss. Insufficient rank never errors — it files a challenge
    the maker resolves (DEC-6, G18)."""

    kind: Literal["reject_proposal"] = "reject_proposal"
    decision_id: int
    rejected_by_user_id: int
    reason: Literal["veto", "dismissed"]


class BulkProposalAction(CommandEnvelope):
    """DEC-7 approver bulk acts — explicit human acts, never clocks (#18)."""

    kind: Literal["bulk_proposal_action"] = "bulk_proposal_action"
    actor_user_id: int
    action: Literal["approve_all", "dismiss_all_from", "dismiss_stale"]
    from_user_id: int | None = None  # dismiss_all_from
    stale_days: int | None = None  # dismiss_stale


class RecordTaskUpdate(CommandEnvelope):
    """Owned by B (`tasks`) but STILL enters via `decisions.service` — the gateway
    routes PIC auto-apply vs authority vs confirm-card (TSK-2 lanes, interface #9).
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
    # contract additions (signals-promotion pipeline; evidence/waiting shapes
    # harvested from PR #53, credit pqminh27): who voiced the mention (promotion
    # proposes in the FIRST reporter's name), per-mention evidence with revision
    # provenance (G45/G65 — no more rev_at_capture=1 hardcode), and the G22
    # free-text counterparty when no party matches.
    reported_by_user_id: int | None = None
    evidence: list[CitationSpec] = Field(default_factory=list)
    waiting_on_text: str | None = None


class AppendCorroboration(CommandEnvelope):
    kind: Literal["append_corroboration"] = "append_corroboration"
    decision_id: int
    citation: CitationSpec


class RegisterReactionAct(CommandEnvelope):
    """DEC-5 chat act (P3 lane A). Present in the union so the shape is frozen
    with the rest; the gateway defers it until P3 opens (plan.md agreement 5).
    """

    kind: Literal["register_reaction_act"] = "register_reaction_act"
    message_id: int
    user_id: int
    emoji: str
    removed: bool = False


Command = Annotated[
    Union[
        ProposeDecision,
        ApproveProposal,
        RejectProposal,
        BulkProposalAction,
        RecordTaskUpdate,
        RecordSignal,
        AppendCorroboration,
        RegisterReactionAct,
    ],
    Field(discriminator="kind"),
]

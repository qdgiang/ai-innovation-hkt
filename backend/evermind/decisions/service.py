"""Owner: A. THE UNIVERSAL COMMAND GATEWAY (architecture.md §The write pipeline).

Every `contracts.commands.Command` — including `RecordTaskUpdate`/`RecordSignal`
owned by B's modules — enters through `DecisionsService.handle`. This is the
ONLY place that may declare something `effective`, append `domain_events`, or
enforce `processed_commands` idempotency. `tasks`/`signals` never process raw
commands; they only project events (see their `consumer.py`).

STUB — P1 deliverable (Lane A: DEC-1..9). B builds against this interface from
day one; do not import decisions.models directly from another module.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.commands import Command
from evermind.decisions.authority import AuthorityResolver
from evermind.decisions.facets import FacetRegistry
from evermind.decisions.gateway import CommandGateway
from evermind.decisions.models import Decision, DecisionCitation
from evermind.decisions.ordering import HandleContext
from evermind.decisions.reader import DecisionReader
from evermind.decisions.task_state import NullTaskStatePort, TaskStatePort
from evermind.org.service import OrgService


class DecisionsService:
    def __init__(self, session: Session, *, task_state: TaskStatePort | None = None):
        self.session = session
        self.task_state = task_state or NullTaskStatePort()
        self.org = OrgService(session)
        self.authority = AuthorityResolver(self.org, self.task_state)
        registry = FacetRegistry.default()
        self.gateway = CommandGateway(
            session,
            org=self.org,
            authority=self.authority,
            registry=registry,
        )
        self.reader = DecisionReader(session, registry)

    def handle(self, command: Command, *, context: HandleContext | None = None) -> dict:
        return self.gateway.handle(command, context)

    def can_decide(self, actor_user_id: int, unit_key: str) -> bool:
        """DEC-4 total authority function; malformed or missing targets fail closed."""
        return self.authority.can_decide(actor_user_id, unit_key)

    def effective_decision_id(self, unit_key: str, *, at: datetime) -> int | None:
        return self.reader.effective_decision_id(unit_key, at=at)

    def tracked_message_ids(self) -> set[int]:
        """Source/citation messages of currently pending decisions (interface #8)."""
        return set(
            self.session.scalars(
                select(DecisionCitation.message_id)
                .join(Decision, Decision.id == DecisionCitation.decision_id)
                .where(Decision.status == "proposed")
            )
        )

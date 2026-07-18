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

from sqlalchemy.orm import Session

from evermind.contracts.commands import Command


class DecisionsService:
    def __init__(self, session: Session):
        self.session = session

    def handle(self, command: Command) -> dict:
        """TODO(A):
        1. processed_commands idempotency check (client_command_id) [EVM-021]
        2. authorization: can_decide(actor, unit) — DEC-4
        3. one transaction: insert + flip predecessor + sweep same-unit proposeds
           + same-value guard (G66) — DEC-3
        4. append domain_events in the same transaction (D3)
        Returns the command outcome (also the shape stored in processed_commands.outcome).
        """
        raise NotImplementedError

    def can_decide(self, actor_user_id: int, unit_key: str) -> bool:
        """TODO(A): DEC-4 — total function; rank gate + delegation + rootless fallback."""
        raise NotImplementedError

    def tracked_message_ids(self) -> set[int]:
        """TODO(A): interface #8 (work-split.md) — reaction_acts are recorded only on
        tracked messages (source messages of pending records). `connectors` (B) consults
        this before writing a reaction_act (G67).
        """
        raise NotImplementedError

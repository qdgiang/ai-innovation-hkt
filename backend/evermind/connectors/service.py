"""Owner: B. Message store + read port consumed by `ingestion` (A) — the ONLY
legal way A's windows see messages (work-split.md interface #1: "never direct
table access").
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message, MessageRevision


class ConnectorsService:
    def __init__(self, session: Session):
        self.session = session

    def read_window(self, group_id: int, from_seq: int, to_seq: int) -> list[Message]:
        """Read-only window slice for `ingestion.service.run_window`. CAP-1/CAP-2."""
        stmt = (
            select(Message)
            .where(Message.group_id == group_id)
            .where(Message.id >= from_seq, Message.id <= to_seq)
            .order_by(Message.id)
        )
        return list(self.session.scalars(stmt))

    def current_text(self, message_id: int) -> tuple[str, int]:
        """(text, rev) at the current revision — for citation `rev_at_capture`/`rev_at_act`."""
        msg = self.session.get(Message, message_id)
        if msg is None:
            raise LookupError(f"message {message_id} not found")
        return msg.text, msg.current_rev

    def apply_edit(self, message_id: int, new_text: str, edited_at) -> None:
        """G45 — append a new message_revisions row, never overwrite `messages.text`."""
        msg = self.session.get(Message, message_id)
        if msg is None:
            raise LookupError(f"message {message_id} not found")
        msg.current_rev += 1
        self.session.add(
            MessageRevision(message_id=message_id, rev=msg.current_rev, text=new_text,
                             edited_at=edited_at)
        )
        msg.text = new_text

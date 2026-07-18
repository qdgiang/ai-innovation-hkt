"""Owner: B. Message store + read port consumed by `ingestion` (A) — the ONLY
legal way A's windows see messages (work-split.md interface #1: "never direct
table access").
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message, MessageRevision


def _capture_time(message: Message) -> datetime:
    value = getattr(message, "captured_at", message.ts)
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


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

    def read_pending(self, group_id: int, *, after: datetime, limit: int,
                     after_id: int = 0) -> list[Message]:
        """Time-ordered unprocessed slice for the extraction lane (ING-2).

        Ordered by capture tuple `(captured_at, id)`. The strict tuple cursor
        makes a bounded page safe even when many rows share a timestamp.
        """
        captured_at = getattr(Message, "captured_at", Message.ts)
        stmt = (
            select(Message)
            .where(Message.group_id == group_id,
                   or_(captured_at > after,
                       and_(captured_at == after, Message.id > after_id)),
                   Message.tombstoned_at.is_(None))
            .order_by(captured_at, Message.id)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def hydrate_context(self, group_id: int, pending: list[Message], *,
                        tail_limit: int = 10, reply_depth: int = 2) -> list[Message]:
        """Return citable history only; callers keep pending anchors separate."""
        if not pending:
            return []
        pending_ids = {message.id for message in pending}
        captured_at = getattr(Message, "captured_at", Message.ts)
        first = min(_capture_time(message) for message in pending)
        tail = list(self.session.scalars(
            select(Message).where(Message.group_id == group_id, captured_at < first,
                                  Message.tombstoned_at.is_(None))
            .order_by(captured_at.desc(), Message.id.desc()).limit(tail_limit)
        ))
        by_id = {message.id: message for message in tail}
        wanted = {message.thread_ref for message in pending if message.thread_ref}
        visited: set[int] = set()
        for _ in range(reply_depth):
            wanted -= pending_ids | visited
            if not wanted:
                break
            visited |= wanted
            parents = list(self.session.scalars(
                select(Message).where(Message.group_id == group_id,
                                      Message.id.in_(wanted),
                                      Message.tombstoned_at.is_(None))
            ))
            by_id.update({message.id: message for message in parents})
            wanted = {message.thread_ref for message in parents if message.thread_ref}
        return sorted(by_id.values(), key=lambda message: (
            _capture_time(message), message.id
        ))

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

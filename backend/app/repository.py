"""Persistence helpers. The >=1-citation contract is enforced here for every
engine; Postgres additionally enforces it with a deferred constraint trigger
(infra/schema.sql). A Record reaching the DB without a Citation is a bug.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from ai.schemas import Message, Record
from backend.app.models import MessageRow, RecordRow, RecordSourceRow


class CitationRequiredError(ValueError):
    def __init__(self, record_id: str) -> None:
        super().__init__(f"record {record_id!r} has no citations — contract violation")


def save_message(session: Session, message: Message) -> MessageRow:
    row = MessageRow(**message.model_dump())  # python mode: ts stays a datetime
    session.add(row)
    return row


def save_record(
    session: Session, record: Record, citation_message_ids: Sequence[str]
) -> RecordRow:
    if not citation_message_ids:
        raise CitationRequiredError(record.id)
    row = RecordRow(
        id=record.id,
        type=record.type.value,
        title=record.title,
        body=record.body.model_dump(mode="json"),
        team=record.team,
        created_from=record.created_from.value,
        confidence=record.confidence,
        status=record.status.value,
    )
    session.add(row)
    for message_id in dict.fromkeys(citation_message_ids):  # dedup, keep order
        session.add(RecordSourceRow(record_id=record.id, message_id=message_id))
    return row

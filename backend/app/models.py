"""SQLAlchemy models mirroring the frozen contracts (ai/schemas.py).

Postgres-only enforcement (constraint trigger for >=1 citation, message
immutability trigger) lives in infra/schema.sql; SQLite dev relies on the
app-level check in repository.save_record. Keep the two in sync.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text)


class MessageRow(Base):
    """Immutable once ingested — source evidence never mutates."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("source IN ('telegram','transcript','replay')", name="ck_messages_source"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    team: Mapped[str | None] = mapped_column(ForeignKey("teams.name"))
    author: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    thread_ref: Mapped[str | None] = mapped_column(Text)
    raw_ref: Mapped[str] = mapped_column(Text, nullable=False)


class RecordRow(Base):
    __tablename__ = "records"
    __table_args__ = (
        CheckConstraint("type IN ('decision','blocker','status')", name="ck_records_type"),
        CheckConstraint("created_from IN ('marker','llm')", name="ck_records_created_from"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_records_confidence"),
        CheckConstraint(
            "status IN ('active','superseded','rejected')", name="ck_records_status"
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[dict] = mapped_column(JSON, nullable=False)
    team: Mapped[str | None] = mapped_column(ForeignKey("teams.name"))
    created_from: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RecordSourceRow(Base):
    """Citation join table — every record must have >=1 row here."""

    __tablename__ = "record_sources"

    record_id: Mapped[str] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), primary_key=True)


class DigestRow(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    team: Mapped[str | None] = mapped_column(ForeignKey("teams.name"))
    period_start: Mapped[dt.date] = mapped_column(nullable=False)
    period_end: Mapped[dt.date] = mapped_column(nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

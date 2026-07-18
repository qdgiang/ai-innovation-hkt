"""Owner: A. Tables: ingest_cursors, extraction_windows, materializations, uploads,
speaker_maps (data-model.md §Ingestion state; architecture.md module table).

Reads messages via `connectors.service` (B) — a read-only service port, never
`connectors.models` directly (work-split.md interface #1).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from evermind.db.base import Base


class IngestCursor(Base):
    """Advances ONLY when window outputs persist (ING-2 transactional guarantee)."""

    __tablename__ = "ingest_cursors"

    group_id: Mapped[int] = mapped_column(primary_key=True)
    high_water_seq: Mapped[int] = mapped_column(default=0)


class ExtractionWindow(Base):
    __tablename__ = "extraction_windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int | None]  # null = bulk upload
    source: Mapped[str]
    from_seq: Mapped[int]
    to_seq: Mapped[int]
    status: Mapped[str] = mapped_column(default="pending")  # pending|running|done|failed
    attempt: Mapped[int] = mapped_column(default=0)
    tokens_in: Mapped[int | None]
    tokens_out: Mapped[int | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class Materialization(Base):
    """[EVM-002] marker/window dedup — re-extraction of an already-materialized
    command yields `already_materialized`, never a duplicate.
    """

    __tablename__ = "materializations"
    __table_args__ = (
        UniqueConstraint("source_message_id", "command_index", "kind", "unit_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_message_id: Mapped[int]
    command_index: Mapped[int]
    kind: Mapped[str]
    unit_key: Mapped[str]
    decision_id: Mapped[int | None]
    update_id: Mapped[int | None]


class Upload(Base):
    """[EVM-011] txt/md only; re-upload = NEW version row, never overwrite."""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    mime: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    uploaded_at: Mapped[datetime]
    uploaded_by: Mapped[int]


class SpeakerMap(Base):
    """G30 — per-upload; unmapped speaker => their decisions born proposed."""

    __tablename__ = "speaker_maps"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"))
    display_name: Mapped[str]
    user_id: Mapped[int | None]

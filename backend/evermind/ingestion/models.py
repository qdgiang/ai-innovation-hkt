"""Owner: A. Tables: ingest_cursors, extraction_windows, materializations
(data-model.md §Ingestion state).

`uploads`/`speaker_maps` live in `evermind.connectors.models` instead, not
here — despite data-model.md grouping them under "Ingestion state" and
architecture.md's module table mentioning "speaker maps" under `ingestion`.
plan.md's P3 Lane B explicitly assigns "CAP-3 transcript connector + speaker
maps (G29/G30) + uploads versioning" to B, and the writer-owns-the-table
principle (already applied to `db.eventlog` for the same reason) says the
table belongs where CAP-3's upload flow actually writes it. `ingestion`
reads `speaker_maps` for linkage the same way it reads `messages` — via
`connectors.service`, never a direct table import.

Reads messages via `connectors.service` (B) — a read-only service port, never
`connectors.models` directly (work-split.md interface #1).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
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

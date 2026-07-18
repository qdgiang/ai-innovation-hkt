"""The domain event log — shared infra, not a business module.

Lives in `db` (not `decisions`) on purpose: `decisions` (A) is the only writer
(appends in the same transaction as a state change, D3), but every projection
(`tasks`/`signals`/`surfacing`, all B) must read it, and architecture.md's
import rule is strict ("`tasks` imports nothing but `contracts`" — plus `db`,
the shared foundation). Putting the event log table here avoids a `tasks` ->
`decisions` import that import-linter would otherwise correctly reject.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from evermind.db.base import Base


class DomainEvent(Base):
    """Appended IN THE SAME TRANSACTION as the state change (D3); the only input
    to projections/feeds; replayable from zero.
    """

    __tablename__ = "domain_events"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime]
    kind: Mapped[str]
    aggregate: Mapped[str]
    aggregate_id: Mapped[int]
    payload: Mapped[dict] = mapped_column(JSON)
    caused_by_command: Mapped[str | None]


class ProjectionOffset(Base):
    """Each projection consumer (tasks/signals/surfacing/knowledge) owns a row
    keyed by its own consumer name — never shared across consumers.
    """

    __tablename__ = "projection_offsets"

    consumer: Mapped[str] = mapped_column(primary_key=True)
    last_seq: Mapped[int] = mapped_column(default=0)

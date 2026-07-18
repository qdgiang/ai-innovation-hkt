"""Shared declarative base. Owner: A (P0), then each module owns its own tables
(architecture.md: "after 0001, each owner migrates their own tables").
"""
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # architecture.md/G54: "storage stays timezone-aware UTC" for every
    # timestamp in the schema. Centralized here (rather than
    # `mapped_column(DateTime(timezone=True))` repeated on every one of the
    # ~25 `Mapped[datetime]` columns across modules) so no module owner has to
    # remember it column-by-column — every `Mapped[datetime]` gets TIMESTAMPTZ
    # for free. Postgres otherwise silently strips tzinfo on round-trip
    # (TIMESTAMP WITHOUT TIME ZONE), which breaks any `now - row.ts` arithmetic
    # the moment `now` is timezone-aware (as `datetime.now(timezone.utc)` is).
    type_annotation_map = {datetime: DateTime(timezone=True)}

"""Owner: B. Tables: feed_entries, inbox_items (data-model.md §Surfacing read models).

Digest/retrospective are COMPUTED VIEWS over decisions/tasks/signals — not
hand-maintained tables (SRF-3/SRF-4); no model classes for them here.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from evermind.db.base import Base


class FeedEntry(Base):
    """Per DECISION not per task; batched ~30min; retractions APPEND and link back
    to the original entry (symmetry rule)."""

    __tablename__ = "feed_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    persona_user_id: Mapped[int]
    ts: Mapped[datetime]
    kind: Mapped[str]
    decision_id: Mapped[int | None]
    task_id: Mapped[int | None]
    payload: Mapped[dict] = mapped_column(JSON)
    batch_key: Mapped[str]
    superseded_by_entry: Mapped[int | None] = mapped_column(ForeignKey("feed_entries.id"))


class InboxItem(Base):
    """Proposals ALWAYS land here + the team pending queue (pending != invisible).
    Capture receipts [EVM-022]: target/UNLINKED, current/proposed values, required
    approver, "projection has not changed".
    """

    __tablename__ = "inbox_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    persona_user_id: Mapped[int]
    kind: Mapped[str]  # proposal | confirm | challenge | diff | triage | receipt
    ref_id: Mapped[int]
    created_at: Mapped[datetime]
    resolved_at: Mapped[datetime | None]
    resolution: Mapped[str | None]

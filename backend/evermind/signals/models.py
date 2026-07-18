"""Owner: B. Table: signals — the weak-signal ledger (data-model.md §Signals).

`parties` lives in `org` (A) — this module consumes `org.service.match_party_alias`,
never the `parties` table directly.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from evermind.contracts.enums import SignalKind, SignalStatus
from evermind.db.base import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[SignalKind]
    project_id: Mapped[int]
    task_id: Mapped[int | None]
    party_id: Mapped[int | None]
    # [EVM-013] identity key = (project, task?, party?, normalized_topic) — prevents
    # false merges across topics; enforce uniqueness in service, not a DB constraint
    # (task?/party? are nullable dimensions of the same key).
    normalized_topic: Mapped[str]
    excerpt: Mapped[str]
    message_id: Mapped[int]
    ts: Mapped[datetime]
    window_id: Mapped[int]
    status: Mapped[SignalStatus] = mapped_column(default=SignalStatus.OPEN)

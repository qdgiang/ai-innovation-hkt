"""Owner: B. CAP-5 — capture health monitoring: a severed feed is never
presented as a quiet week (G53).

`chat_groups` (the set of *mapped* groups) lives in `org`, which `connectors`
may not import — so "which groups exist" is approximated here as "every
group_id ever seen in `messages`". A group that was mapped but has NEVER
received a single message would be invisible to this check; that's a real
gap versus the full G53 spec (which self-checks every mapped group, seen or
not), not a bug in what's implemented.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message

DEFAULT_SILENCE_DAYS = 2


class CaptureHealthService:
    def __init__(self, session: Session):
        self.session = session

    def check_all_groups(self, *, now: datetime | None = None,
                          silence_days: int = DEFAULT_SILENCE_DAYS) -> list[dict]:
        """One row per group that has ever produced a message, flagging
        `dark: true` when nothing has arrived in `silence_days`.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=silence_days)

        group_ids = self.session.scalars(
            select(Message.group_id).where(Message.group_id.is_not(None)).distinct()
        ).all()

        report = []
        for group_id in group_ids:
            last_ts = self.session.scalar(
                select(Message.ts).where(Message.group_id == group_id)
                .order_by(Message.ts.desc()).limit(1)
            )
            dark = last_ts is None or last_ts < cutoff
            report.append({"group_id": group_id, "last_message_at": last_ts, "dark": dark})
        return report

"""L1 — CAP-5 capture health (plan.md P6, G53: a severed feed is never
presented as a quiet week)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from evermind.connectors.health import CaptureHealthService
from evermind.connectors.models import Message

T0 = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _msg(id_: int, group_id: int, ts: datetime) -> Message:
    return Message(id=id_, source="replay", group_id=group_id, author_identity="linh",
                    ts=ts, text="x", raw_ref=f"corpus.jsonl:{id_}")


def test_recently_active_group_is_not_dark(db_session: Session):
    db_session.add(_msg(1, 7, T0 - timedelta(hours=1)))
    db_session.flush()

    report = CaptureHealthService(db_session).check_all_groups(now=T0)
    row = next(r for r in report if r["group_id"] == 7)
    assert row["dark"] is False


def test_silent_group_is_flagged_dark(db_session: Session):
    db_session.add(_msg(1, 7, T0 - timedelta(days=5)))
    db_session.flush()

    report = CaptureHealthService(db_session).check_all_groups(now=T0, silence_days=2)
    row = next(r for r in report if r["group_id"] == 7)
    assert row["dark"] is True


def test_reports_every_group_that_has_ever_had_a_message(db_session: Session):
    db_session.add(_msg(1, 7, T0))
    db_session.add(_msg(2, 8, T0 - timedelta(days=10)))
    db_session.flush()

    report = CaptureHealthService(db_session).check_all_groups(now=T0)
    group_ids = {r["group_id"] for r in report}
    assert group_ids == {7, 8}

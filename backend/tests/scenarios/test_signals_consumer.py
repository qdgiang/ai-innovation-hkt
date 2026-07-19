"""L1 — the signals event-consumer (SIG-1 ledger fold): `signal_recorded`
domain events -> ledger rows, offset-idempotent. Mirror of the tasks fold
suite's synthetic-events approach.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import SignalKind, SignalStatus
from evermind.db.eventlog import DomainEvent
from evermind.signals.consumer import SignalsConsumer
from evermind.signals.models import Signal

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _signal_recorded(session: Session, *, message_id: int, topic: str,
                     task_id: int | None = None, party_id: int | None = None,
                     reported_by_user_id: int | None = None) -> DomainEvent:
    event = DomainEvent(
        ts=T0, kind="signal_recorded", aggregate="signal",
        aggregate_id=task_id or 0,
        payload={"signal_kind": "blocker", "project_id": 1, "task_id": task_id,
                 "party_id": party_id, "normalized_topic": topic,
                 "excerpt": f"excerpt {message_id}", "message_id": message_id,
                 "ts": T0.isoformat(), "window_id": 7,
                 "reported_by_user_id": reported_by_user_id},
    )
    session.add(event)
    session.flush()
    return event


def test_signal_recorded_folds_a_ledger_row(db_session: Session):
    _signal_recorded(db_session, message_id=41, topic="xưởng in chưa báo giá",
                     party_id=9, reported_by_user_id=3)

    applied = SignalsConsumer(db_session).poll_and_apply()

    assert applied == 1
    signal = db_session.scalar(select(Signal))
    assert signal.kind is SignalKind.BLOCKER
    assert signal.status is SignalStatus.OPEN
    assert signal.normalized_topic == "xưởng in chưa báo giá"
    assert signal.message_id == 41
    assert signal.party_id == 9
    assert signal.reported_by_user_id == 3
    assert signal.window_id == 7


def test_consumer_offset_is_idempotent(db_session: Session):
    _signal_recorded(db_session, message_id=41, topic="a")
    consumer = SignalsConsumer(db_session)
    assert consumer.poll_and_apply() == 1
    assert consumer.poll_and_apply() == 0  # nothing re-folds

    _signal_recorded(db_session, message_id=42, topic="a")
    assert consumer.poll_and_apply() == 1  # only the new event
    assert db_session.scalars(select(Signal)).all().__len__() == 2


def test_consumer_skips_foreign_event_kinds(db_session: Session):
    event = DomainEvent(ts=T0, kind="decision_effective", aggregate="decision",
                        aggregate_id=1, payload={"decision_id": 1, "ops": []})
    db_session.add(event)
    db_session.flush()

    assert SignalsConsumer(db_session).poll_and_apply() == 0
    assert db_session.scalar(select(Signal)) is None


def test_malformed_event_is_quarantined_and_offset_advances(db_session: Session):
    """PR #53 pattern: a poison event must never pin the projection — it's
    logged, skipped, and the offset still moves past it."""
    bad = DomainEvent(ts=T0, kind="signal_recorded", aggregate="signal",
                      aggregate_id=0, payload={"signal_kind": "blocker"})  # missing keys
    db_session.add(bad)
    db_session.flush()
    _signal_recorded(db_session, message_id=77, topic="lành lặn")

    consumer = SignalsConsumer(db_session)
    applied = consumer.poll_and_apply()

    assert applied == 1  # only the healthy event folded
    signal = db_session.scalar(select(Signal))
    assert signal.message_id == 77
    assert consumer.poll_and_apply() == 0  # offset moved PAST the poison event


def test_content_dedupe_survives_offset_reset(db_session: Session):
    """Replay past a reset offset (manual event-log repair) never duplicates."""
    from evermind.db.eventlog import ProjectionOffset

    _signal_recorded(db_session, message_id=41, topic="a")
    consumer = SignalsConsumer(db_session)
    consumer.poll_and_apply()
    db_session.get(ProjectionOffset, "signals").last_seq = 0  # simulate repair

    assert consumer.poll_and_apply() == 0  # dedupe caught it
    assert len(db_session.scalars(select(Signal)).all()) == 1

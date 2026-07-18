"""L1 — SIG-1 signal ledger, emit-only (plan.md P2 Lane B). Derived from S8
(the invisible blocker, B-2 in data-v2): a signal is never promoted on its own
mention; promotion (counting + deciding) lands in P3.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from evermind.contracts.enums import SignalKind, SignalStatus
from evermind.signals.models import Signal
from evermind.signals.service import SignalsService

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_emit_appends_an_open_signal(db_session: Session):
    signal_id = SignalsService(db_session).emit(
        kind=SignalKind.BLOCKER, project_id=1, normalized_topic="sound-supplier",
        excerpt="âm thanh bên đó chưa thấy trả lời", message_id=42, ts=T0, window_id=1,
    )
    signal = db_session.get(Signal, signal_id)
    assert signal is not None
    assert signal.status == SignalStatus.OPEN
    assert signal.kind == SignalKind.BLOCKER


def test_single_mention_never_auto_promotes(db_session: Session):
    """The ledger only ever appends — a single call never flips anything to
    `blocked`; that's P3's `try_promote` job, not `emit`."""
    SignalsService(db_session).emit(
        kind=SignalKind.BLOCKER, project_id=1, normalized_topic="sound-supplier",
        excerpt="mention one", message_id=1, ts=T0, window_id=1,
    )
    open_signals = SignalsService(db_session).open_signals_for_identity(
        project_id=1, normalized_topic="sound-supplier",
    )
    assert len(open_signals) == 1
    assert open_signals[0].status == SignalStatus.OPEN


def test_accumulates_mentions_across_windows_for_same_identity(db_session: Session):
    """Mirrors B-2: three passing mentions across windows, none marked `!blocked`."""
    service = SignalsService(db_session)
    for i, ts in enumerate([T0, T0 + timedelta(days=1), T0 + timedelta(days=3)]):
        service.emit(
            kind=SignalKind.BLOCKER, project_id=1, normalized_topic="sound-supplier",
            excerpt=f"mention {i}", message_id=100 + i, ts=ts, window_id=i,
        )
    accumulated = service.open_signals_for_identity(
        project_id=1, normalized_topic="sound-supplier",
    )
    assert len(accumulated) == 3
    assert [s.ts for s in accumulated] == sorted(s.ts for s in accumulated)


def test_identity_key_separates_different_topics_and_tasks(db_session: Session):
    """[EVM-013]: (project, task?, party?, normalized_topic) — no false merges."""
    service = SignalsService(db_session)
    service.emit(kind=SignalKind.BLOCKER, project_id=1, normalized_topic="sound-supplier",
                 excerpt="a", message_id=1, ts=T0, window_id=1)
    service.emit(kind=SignalKind.BLOCKER, project_id=1, normalized_topic="printer-vendor",
                 excerpt="b", message_id=2, ts=T0, window_id=1)
    service.emit(kind=SignalKind.BLOCKER, project_id=1, task_id=5,
                 normalized_topic="sound-supplier", excerpt="c", message_id=3, ts=T0, window_id=1)

    sound_project_level = service.open_signals_for_identity(
        project_id=1, normalized_topic="sound-supplier",
    )
    assert len(sound_project_level) == 1  # the task_id=5 one is a DIFFERENT identity

    sound_task_scoped = service.open_signals_for_identity(
        project_id=1, normalized_topic="sound-supplier", task_id=5,
    )
    assert len(sound_task_scoped) == 1

"""L1 — SIG-1 promotion rule + SIG-2 party resolution (plan.md P3 Lane B)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import SignalKind
from evermind.signals import promotion
from evermind.signals.service import SignalsService

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The pure rule (evaluate) — the actual business value, fully testable
# ---------------------------------------------------------------------------


def test_no_signals_never_promotes():
    assert promotion.evaluate([], now=T0) is None


def test_single_fresh_mention_never_promotes(db_session: Session):
    """X-2 (data-v2 distractor): a single passing remark must NOT fire."""
    SignalsService(db_session).emit(
        kind=SignalKind.BLOCKER, project_id=1, normalized_topic="sound-supplier",
        excerpt="mention", message_id=1, ts=T0, window_id=1,
    )
    open_signals = SignalsService(db_session).open_signals_for_identity(
        project_id=1, normalized_topic="sound-supplier",
    )
    decision = promotion.evaluate(open_signals, now=T0 + timedelta(hours=1))
    assert decision is None


def test_two_corroborating_mentions_promote(db_session: Session):
    """Mirrors B-2: 3 passing mentions, never marked !blocked, still promotes
    once corroborated."""
    service = SignalsService(db_session)
    service.emit(kind=SignalKind.BLOCKER, project_id=1, normalized_topic="sound-supplier",
                 excerpt="mention 1", message_id=10, ts=T0, window_id=1)
    service.emit(kind=SignalKind.BLOCKER, project_id=1, normalized_topic="sound-supplier",
                 excerpt="mention 2", message_id=20, ts=T0 + timedelta(days=2), window_id=2)

    open_signals = service.open_signals_for_identity(
        project_id=1, normalized_topic="sound-supplier",
    )
    decision = promotion.evaluate(open_signals, now=T0 + timedelta(days=2, hours=1))
    assert decision is not None
    assert decision.kind == SignalKind.BLOCKER
    assert decision.citation_message_ids == [10, 20]  # G27: ALL accumulated mentions
    assert decision.since == T0


def test_single_stale_mention_promotes(db_session: Session):
    """design-v2.md: "1 + staleness" also promotes, even without corroboration."""
    SignalsService(db_session).emit(
        kind=SignalKind.BLOCKER, project_id=1, normalized_topic="printer-vendor",
        excerpt="mention", message_id=5, ts=T0, window_id=1,
    )
    open_signals = SignalsService(db_session).open_signals_for_identity(
        project_id=1, normalized_topic="printer-vendor",
    )
    fresh = promotion.evaluate(open_signals, now=T0 + timedelta(days=1))
    stale = promotion.evaluate(open_signals, now=T0 + timedelta(days=8))
    assert fresh is None
    assert stale is not None
    assert stale.citation_message_ids == [5]


# ---------------------------------------------------------------------------
# try_promote — wires the rule against the real ledger
# ---------------------------------------------------------------------------


def test_try_promote_returns_none_when_not_eligible(db_session: Session):
    SignalsService(db_session).emit(
        kind=SignalKind.DEPENDENCY, project_id=1, normalized_topic="vendor-x",
        excerpt="mention", message_id=1, ts=T0, window_id=1,
    )
    result = SignalsService(db_session).try_promote(
        project_id=1, normalized_topic="vendor-x", now=T0 + timedelta(hours=1),
    )
    assert result is None


def test_try_promote_returns_a_decision_when_eligible(db_session: Session):
    service = SignalsService(db_session)
    service.emit(kind=SignalKind.DEPENDENCY, project_id=1, normalized_topic="vendor-x",
                 excerpt="a", message_id=1, ts=T0, window_id=1)
    service.emit(kind=SignalKind.DEPENDENCY, project_id=1, normalized_topic="vendor-x",
                 excerpt="b", message_id=2, ts=T0 + timedelta(hours=1), window_id=1)

    result = service.try_promote(
        project_id=1, normalized_topic="vendor-x", now=T0 + timedelta(hours=2),
    )
    assert result is not None
    assert result.kind == SignalKind.DEPENDENCY
    assert result.citation_message_ids == [1, 2]


# ---------------------------------------------------------------------------
# SIG-2 — party resolution (real match/no-match: org.service landed with PR #42)
# ---------------------------------------------------------------------------


def test_resolve_waiting_on_matches_a_seeded_party_alias(db_session: Session, org_ids):
    """G22/SIG-2 — "đang chờ Kim Long" resolves to the vendor party via alias
    containment (match logic: org.service.match_party_alias, Lane A)."""
    resolved = SignalsService(db_session).resolve_waiting_on("đang chờ Kim Long báo giá")
    assert resolved == {"party_id": org_ids["parties"]["PTY-KL"]}


def test_resolve_waiting_on_keeps_free_text_when_no_party_matches(db_session: Session, org_ids):
    """G22 — no forced match: unknown counterparties stay free text."""
    resolved = SignalsService(db_session).resolve_waiting_on("bên giao hàng mới")
    assert resolved == {"waiting_on_text": "bên giao hàng mới"}


# ---------------------------------------------------------------------------
# SIG-1 P3 — promotion_sweep: the full circle
# (ledger -> promote -> PROPOSED blocked-state decision -> human approves ->
#  fold -> blocked task with counterparty context on the board)
# ---------------------------------------------------------------------------


def test_promotion_sweep_full_circle(db_session: Session, org_ids):
    import uuid

    from evermind.contracts.commands import ApproveProposal
    from evermind.contracts.enums import CreatedFrom, SignalStatus, TaskStatus
    from evermind.decisions.models import DecisionCitation
    from evermind.decisions.service import DecisionsService
    from evermind.signals.models import Signal
    from evermind.tasks.consumer import TasksConsumer
    from evermind.tasks.models import Task, TaskTeam
    from evermind.tasks.service import TasksService
    from sqlalchemy import select as _select

    project = org_ids["projects"]["P-TT"]
    team = org_ids["teams"]["TEAM-EV"]
    duc, linh = org_ids["users"]["duc"], org_ids["users"]["linh"]
    kim_long = org_ids["parties"]["PTY-KL"]

    db_session.add(Task(id=901, project_id=project, kind="project",
                        description="Đặt in backdrop", status="doing"))
    db_session.add(TaskTeam(task_id=901, team_id=team))
    # mentions live in the PAST relative to now — a future-ts submission would
    # (correctly) trip the gateway's impossible-chronology triage [EVM-012]
    base = datetime.now(timezone.utc) - timedelta(days=3)
    for day, mid in enumerate((11, 12, 13)):
        db_session.add(Signal(
            kind=SignalKind.BLOCKER, project_id=project, task_id=901,
            party_id=kim_long, normalized_topic="kim long chưa báo giá",
            excerpt=f"nhắc lần {day + 1}", message_id=mid,
            ts=base + timedelta(days=day), window_id=1,
            status=SignalStatus.OPEN, reported_by_user_id=duc))
    db_session.flush()

    service = SignalsService(db_session)
    gateway = DecisionsService(db_session, task_port=TasksService(db_session))
    reports = service.promotion_sweep(decisions_service=gateway,
                                      now=base + timedelta(days=2, hours=1))

    # promoted with ALL mentions as citations (G27); decision born PROPOSED
    assert len(reports) == 1
    assert reports[0]["citations"] == [11, 12, 13]
    assert reports[0]["decision"]["status"] == "proposed"
    decision_id = reports[0]["decision"]["decision_id"]
    assert all(s.status is SignalStatus.PROMOTED
               for s in db_session.scalars(_select(Signal)))

    # the explicit review lane (PR #53 harvest): reason + reporter persisted,
    # and the review routed to the owning team, not just the reporter
    from evermind.decisions.models import Decision as _Decision
    decision = db_session.get(_Decision, decision_id)
    assert decision.review_reason == "signal_promotion"
    assert decision.reported_by_user_id == duc

    # nothing touches the task until a HUMAN confirms (promotion only proposes)
    TasksConsumer(db_session).poll_and_apply()
    assert db_session.get(Task, 901).status == "doing"

    outcome = gateway.handle(ApproveProposal(
        client_command_id=uuid.uuid4(), persona="linh",
        created_from=CreatedFrom.DASHBOARD,
        decision_id=decision_id, approved_by_user_id=linh))
    assert outcome["status"] == "effective"
    TasksConsumer(db_session).poll_and_apply()

    task = db_session.get(Task, 901)
    assert task.status == TaskStatus.BLOCKED
    assert task.blocked_waiting_on_party_id == kim_long
    assert task.blocked_since is not None
    citations = db_session.scalars(_select(DecisionCitation).where(
        DecisionCitation.decision_id == decision_id)).all()
    assert {c.message_id for c in citations} == {11, 12, 13}

    # a second sweep finds no OPEN identity — never re-promotes or re-submits
    assert service.promotion_sweep(decisions_service=gateway,
                                   now=base + timedelta(days=3)) == []


def test_promotion_sweep_never_promotes_asks_or_parked(db_session: Session, org_ids):
    from evermind.contracts.enums import SignalStatus
    from evermind.signals.models import Signal

    project = org_ids["projects"]["P-TT"]
    for day, mid in enumerate((21, 22, 23)):
        db_session.add(Signal(
            kind=SignalKind.ASK, project_id=project, task_id=None, party_id=None,
            normalized_topic="có thuê mc không", excerpt="hỏi lần nữa",
            message_id=mid, ts=T0 + timedelta(days=day), window_id=1,
            status=SignalStatus.OPEN))
    db_session.flush()

    reports = SignalsService(db_session).promotion_sweep(
        now=T0 + timedelta(days=30))

    assert reports == []  # asks age into the digest (G35), never promote
    assert all(s.status is SignalStatus.OPEN
               for s in db_session.scalars(select(Signal)))

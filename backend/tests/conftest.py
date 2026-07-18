"""L1 test harness (testing-strategy.md): scripted commands in → asserted state
out. Real Postgres when TEST_DATABASE_URL points at one (the CI/compose shape);
in-memory SQLite as the no-infra fallback so the pure-domain suites stay
runnable anywhere. Zero LLM, zero platform code.

The invariant sweep (data-model.md §Cross-cutting invariants) runs autouse after
EVERY test — each scenario's end-state is also an invariant check.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from evermind.config import settings
from evermind.db.base import Base

# import every module's models so create_all sees the full schema
from evermind.org import models as _org_models  # noqa: F401
from evermind.connectors import models as _connectors_models  # noqa: F401
from evermind.ingestion import models as _ingestion_models  # noqa: F401
from evermind.decisions import models as _decisions_models  # noqa: F401
from evermind.db import eventlog as _eventlog_models  # noqa: F401
from evermind.tasks import models as _tasks_models  # noqa: F401
from evermind.signals import models as _signals_models  # noqa: F401
from evermind.surfacing import models as _surfacing_models  # noqa: F401

from evermind.contracts.commands import CitationSpec, OpSpec, ProposeDecision
from evermind.contracts.enums import (
    CitationKind, CreatedFrom, DecisionScope, DecisionStatus, TaskStatus,
)
from evermind.contracts.ports import TaskView
from evermind.decisions.models import Decision, DecisionCitation, DecisionUnit, EffectiveUnit
from evermind.decisions.service import DecisionsService
from evermind.org.seed import load_org_seed
from evermind.org.service import OrgService

# Real Postgres by default (settings.database_url reads DATABASE_URL — the CI/
# compose shape; testing-strategy.md: L1 runs on real Postgres). SQLite in-memory
# is an explicit opt-in via TEST_DATABASE_URL for no-infra runs — NOT the default,
# else CI would silently downgrade to SQLite (it sets DATABASE_URL, not TEST_*).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or settings.database_url
ORG_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data-v2", "org.json")


def utcnow() -> datetime:
    # timezone-AWARE: every timestamp column is TIMESTAMPTZ (db/base.py, G54) —
    # naive values would TypeError against aware read-backs.
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Zero LLM (this file's header contract): even when the container carries a
    real AI_API_KEY, tests must stay hermetic — force LLMUnavailable so
    KnowledgeService returns its deterministic structured fallback."""
    monkeypatch.setattr(settings, "ai_api_key", "", raising=False)


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    """Fresh rows per test: schema persists, data is wiped."""
    with Session(engine) as wipe:
        for table in reversed(Base.metadata.sorted_tables):
            wipe.execute(table.delete())
        wipe.commit()
    # autoflush stays ON (the default): B's fold tests add domain_events and
    # expect the consumer's next SELECT to see them; A's service flushes
    # explicitly everywhere, so it is indifferent. (Prod sessions differ —
    # db/session.py uses autoflush=False; modules that need visibility flush,
    # see tasks/merge.py.)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def org_ids(db_session) -> dict:
    """The data-v2 org seed; returns slug→id maps (users keyed by handle)."""
    return load_org_seed(db_session, ORG_SEED_PATH)


@pytest.fixture
def org(db_session) -> OrgService:
    return OrgService(db_session)


class FakeTaskPort:
    """Interface #9 stand-in until B's fold lands (plan.md P1 Lane B note:
    'fold tested against synthetic domain_events until A's gateway lands' —
    symmetrically, A's gateway tests against a synthetic task projection)."""

    def __init__(self):
        self.tasks: dict[int, TaskView] = {}

    def add(self, task_id: int, project_id: int, *, status: str = "todo",
            team_ids: list[int] | None = None, pics: list[int] | None = None,
            merged_into: int | None = None) -> TaskView:
        view = TaskView(id=task_id, project_id=project_id, status=TaskStatus(status),
                        team_ids=team_ids or [], pic_user_ids=pics or [],
                        merged_into=merged_into)
        self.tasks[task_id] = view
        return view

    def get_task_view(self, task_id: int) -> TaskView | None:
        return self.tasks.get(task_id)


@pytest.fixture
def task_port() -> FakeTaskPort:
    return FakeTaskPort()


@pytest.fixture
def service(db_session, task_port) -> DecisionsService:
    return DecisionsService(db_session, task_port=task_port, tau=0.8)


# ── command builders ─────────────────────────────────────────────────────


def cite(message_id: int = 1, kind: CitationKind = CitationKind.EVIDENCE) -> CitationSpec:
    return CitationSpec(message_id=message_id, kind=kind, rev_at_capture=1)


def propose(
    maker: int,
    ops: list[OpSpec],
    *,
    scope: DecisionScope = DecisionScope.TASK,
    scope_target: str | None = None,
    created_from: CreatedFrom = CreatedFrom.MARKER,
    confidence: float | None = None,
    ts: datetime | None = None,
    citations: list[CitationSpec] | None = None,
    description: str = "test decision",
    **kwargs,
) -> ProposeDecision:
    return ProposeDecision(
        client_command_id=uuid.uuid4(),
        persona=f"user-{maker}",
        created_from=created_from,
        confidence=confidence,
        ts=ts,
        decided_by_user_id=maker,
        scope=scope,
        scope_target=scope_target or (ops[0].target if ops else "task:1"),
        description=description,
        ops=ops,
        citations=citations if citations is not None else [cite()],
        **kwargs,
    )


def op_set(target: str, facet: str, value) -> OpSpec:
    return OpSpec(target=target, facet=facet, op="set", value=value)


@pytest.fixture
def mk():
    """Namespace of builders for terser tests."""
    class _NS:
        cite = staticmethod(cite)
        propose = staticmethod(propose)
        op_set = staticmethod(op_set)
        OpSpec = OpSpec
        now = staticmethod(utcnow)
        ago = staticmethod(lambda **kw: utcnow() - timedelta(**kw))
    return _NS


# ── the invariant sweep (autouse — data-model.md §Cross-cutting invariants) ──


@pytest.fixture(autouse=True)
def invariant_sweep(request):
    session: Session | None = (
        request.getfixturevalue("db_session")
        if "db_session" in request.fixturenames else None
    )
    yield
    if session is None or not session.is_active:
        return
    decisions = list(session.scalars(select(Decision)))

    for decision in decisions:
        # invariant 1: chat-originated decisions carry >=1 evidence citation
        if decision.created_from in (CreatedFrom.MARKER, CreatedFrom.LLM):
            evidence = session.scalar(select(DecisionCitation).where(
                DecisionCitation.decision_id == decision.id,
                DecisionCitation.kind == CitationKind.EVIDENCE))
            assert evidence is not None, (
                f"invariant 1 violated: decision {decision.id} "
                f"({decision.created_from}) has no evidence citation")
        # invariant 4 shape: rejected carries a reason; superseded carries a link
        if decision.status is DecisionStatus.REJECTED:
            assert decision.rejected_reason is not None, (
                f"invariant 4: rejected decision {decision.id} lacks rejected_reason")
        if decision.status is DecisionStatus.SUPERSEDED:
            assert decision.superseded_by_decision_id is not None, (
                f"invariant 4: superseded decision {decision.id} lacks superseded_by")
        # invariant 7: no TTL — the model simply has no such column; assert the
        # rejected_reason vocabulary never grew an "expired"
        if decision.rejected_reason is not None:
            assert decision.rejected_reason.value in (
                "veto", "overruled", "withdrawn", "dismissed")

    # invariant 2: at most one effective (non-window) decision per unit
    unit_owners: dict[str, int] = {}
    rows = session.execute(
        select(DecisionUnit.unit_key, Decision)
        .join(Decision, Decision.id == DecisionUnit.decision_id)
        .where(Decision.status == DecisionStatus.EFFECTIVE)
    ).all()
    for unit_key, decision in rows:
        if decision.effect_window_from is not None:
            continue  # shadows, never occupies (G42)
        assert unit_owners.setdefault(unit_key, decision.id) == decision.id, (
            f"invariant 2 violated: unit {unit_key} has two effective decisions "
            f"({unit_owners[unit_key]}, {decision.id})")
        occupant = session.scalar(select(EffectiveUnit.decision_id).where(
            EffectiveUnit.unit_key == unit_key))
        assert occupant == decision.id, (
            f"effective_units drift on {unit_key}: index says {occupant}, "
            f"decision {decision.id} is effective")

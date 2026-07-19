"""Regression coverage for the evidence-backed Blocker Radar path."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from evermind.api.routers.decisions_router import _serialize
from evermind.api.routers.signals_router import list_blockers
from evermind.api.routers.workspace_router import workspace
from evermind.connectors.models import Message
from evermind.contracts.commands import ApproveProposal, CitationSpec, RecordSignal, RejectProposal
from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionStatus, SignalStatus, TaskKind, TaskStatus
from evermind.db.eventlog import DomainEvent, ProjectionOffset
from evermind.decisions.models import Decision, DecisionCitation
from evermind.decisions.service import DecisionsService
from evermind.ingestion.extraction import ExtractedCandidate, ExtractionResult
from evermind.ingestion.service import IngestionService
from evermind.llm.client import LLMCallResult
from evermind.org.service import OrgService
from evermind.signals.consumer import CONSUMER_NAME, SignalsConsumer
from evermind.signals.models import Signal
from evermind.tasks.consumer import TasksConsumer
from evermind.tasks.models import Task, TaskTeam
from evermind.tasks.service import TasksService


class _Gateway:
    def __init__(self, result: ExtractionResult):
        self.result = result

    def call_json(self, *, system: str, user: str, schema):
        return self.result, LLMCallResult(model="test", tokens_in=1, tokens_out=1,
                                          latency_ms=1, validation_attempts=1)


def _task(db_session, org_ids, *, task_id: int = 801, start_date=None) -> Task:
    task = Task(
        id=task_id, project_id=org_ids["projects"]["P-TT"], kind=TaskKind.PROJECT,
        description="Chờ nhà cung cấp phản hồi", status=TaskStatus.TODO,
        start_date=start_date, end_date=None, end_date_defaulted=False,
        merged_into=None, parent_task_id=None, blocked_waiting_on_party_id=None,
        blocked_waiting_on_text=None, blocked_since=None, note=None,
    )
    db_session.add_all([task, TaskTeam(task_id=task_id, team_id=org_ids["teams"]["TEAM-EV"])])
    db_session.flush()
    return task


def _record_signal(db_session, org_ids, *, task_id: int, message_id: int,
                   topic: str = "vendor-response", ts=None, revision: int = 1):
    actor = org_ids["users"]["duc"]
    return DecisionsService(db_session, task_port=TasksService(db_session)).handle(
        RecordSignal(
            client_command_id=uuid.uuid4(), persona="duc", created_from=CreatedFrom.LLM,
            confidence=0.9, ts=ts or datetime.now(timezone.utc), source_message_id=message_id,
            window_id=1, signal_kind="blocker", project_id=org_ids["projects"]["P-TT"],
            task_id=task_id, normalized_topic=topic, excerpt="Nhà cung cấp vẫn chưa phản hồi",
            waiting_on_text="Kim Long", reported_by_user_id=actor,
            evidence=[CitationSpec(message_id=message_id, kind=CitationKind.EVIDENCE,
                                   rev_at_capture=revision)],
        ), commit=False,
    )


def test_llm_weak_blocker_materializes_only_for_an_open_task(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    task = _task(db_session, org_ids)
    now = datetime.now(timezone.utc)
    db_session.add(Message(id=8811, source="replay", group_id=group_id, author_identity="duc",
                           ts=now - timedelta(minutes=30), text="Kim Long chưa báo giá", thread_ref=None,
                           raw_ref="test:8811", kind="text"))
    db_session.flush()
    valid = ExtractedCandidate(kind="weak_blocker", description="Chờ Kim Long báo giá",
                               task_id=task.id, normalized_topic="vendor-quote",
                               waiting_on_text="Kim Long", decided_by_message_id=8811,
                               evidence_message_ids=[8811], confidence=0.8)
    result = IngestionService(db_session).run_window(group_id, gateway=_Gateway(ExtractionResult(candidates=[valid])))
    assert result["outcomes"][0]["status"] == "signal_recorded"
    SignalsConsumer(db_session).poll_and_apply()
    assert db_session.scalar(select(Signal).where(Signal.task_id == task.id)) is not None

    db_session.add(Message(id=8812, source="replay", group_id=group_id, author_identity="duc",
                           ts=now - timedelta(minutes=20), text="Vẫn chờ", thread_ref=None,
                           raw_ref="test:8812", kind="text"))
    db_session.flush()
    invalid = ExtractedCandidate(kind="weak_blocker", description="Bịa task",
                                 task_id=999999, normalized_topic="fake",
                                 decided_by_message_id=8812, evidence_message_ids=[8812], confidence=0.8)
    # Advance the extraction cursor only enough to exercise candidate validation.
    result = IngestionService(db_session).run_window(group_id, gateway=_Gateway(ExtractionResult(candidates=[invalid])))
    assert result["outcomes"][0]["status"] == "invalid_weak_blocker"


def test_two_signals_create_one_proposal_with_receipts_and_do_not_block_preapproval(db_session, org_ids):
    task = _task(db_session, org_ids)
    _record_signal(db_session, org_ids, task_id=task.id, message_id=8821, revision=3)
    _record_signal(db_session, org_ids, task_id=task.id, message_id=8822, revision=5)
    consumer = SignalsConsumer(db_session)
    consumer.poll_and_apply()

    decisions = list(db_session.scalars(select(Decision).where(Decision.review_reason == "signal_promotion")))
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.status is DecisionStatus.PROPOSED
    assert decision.reported_by_user_id == org_ids["users"]["duc"]
    assert db_session.get(Task, task.id).status is TaskStatus.TODO
    citations = list(db_session.scalars(select(DecisionCitation).where(DecisionCitation.decision_id == decision.id)))
    assert {(c.message_id, c.rev_at_capture) for c in citations} == {(8821, 3), (8822, 5)}
    serialized = _serialize(decision, citations, {org_ids["users"]["duc"]: "duc"})
    assert serialized["decided_by_user_id"] is None
    assert serialized["reported_by_handle"] == "duc"

    # A second sweep must not create a duplicate proposal after its signals are promoted.
    assert consumer.promote_eligible() == 0
    assert len(list(db_session.scalars(select(Decision).where(Decision.review_reason == "signal_promotion")))) == 1
    assert {s.status for s in db_session.scalars(select(Signal))} == {SignalStatus.PROMOTED}


def test_malformed_signal_event_is_quarantined_and_offset_advances(db_session):
    db_session.add(DomainEvent(ts=datetime.now(timezone.utc), kind="signal_recorded", aggregate="signal",
                               aggregate_id=0, payload={"project_id": 1}, caused_by_command=None))
    db_session.flush()
    assert SignalsConsumer(db_session).poll_and_apply() == 1
    assert db_session.get(ProjectionOffset, CONSUMER_NAME).last_seq == 1


def test_rejected_signal_promotion_is_not_resubmitted_without_new_evidence(db_session, org_ids):
    task = _task(db_session, org_ids)
    _record_signal(db_session, org_ids, task_id=task.id, message_id=8841)
    _record_signal(db_session, org_ids, task_id=task.id, message_id=8842)
    consumer = SignalsConsumer(db_session)
    consumer.poll_and_apply()
    decision = db_session.scalar(select(Decision).where(Decision.review_reason == "signal_promotion"))
    assert decision is not None and decision.status is DecisionStatus.PROPOSED
    rejected = DecisionsService(db_session, task_port=TasksService(db_session)).handle(RejectProposal(
        client_command_id=uuid.uuid4(), persona="minh", created_from=CreatedFrom.DASHBOARD,
        decision_id=decision.id, rejected_by_user_id=org_ids["users"]["minh"], reason="dismissed",
    ), commit=False)
    assert rejected["status"] == "rejected"
    assert consumer.promote_eligible() == 0
    assert len(list(db_session.scalars(select(Decision).where(Decision.review_reason == "signal_promotion")))) == 1


def test_stale_single_signal_creates_a_proposed_blocker_in_the_daily_sweep(db_session, org_ids):
    task = _task(db_session, org_ids)
    now = datetime.now(timezone.utc)
    _record_signal(db_session, org_ids, task_id=task.id, message_id=8851, ts=now - timedelta(days=8))
    consumer = SignalsConsumer(db_session)
    consumer.poll_and_apply()
    assert db_session.scalar(select(Decision).where(Decision.review_reason == "signal_promotion")) is None
    assert consumer.promote_eligible(now=now) == 1
    decision = db_session.scalar(select(Decision).where(Decision.review_reason == "signal_promotion"))
    assert decision is not None and decision.status is DecisionStatus.PROPOSED
    # The daily sweep has no event payload.  It must retain the person whose
    # Telegram evidence created this signal, rather than substituting a task PIC.
    assert decision.reported_by_user_id == org_ids["users"]["duc"]


def test_blockers_board_is_project_scoped_authorized_and_resolves_party_label(db_session, org_ids):
    task = _task(db_session, org_ids)
    task.status = TaskStatus.BLOCKED
    task.blocked_waiting_on_party_id = org_ids["parties"]["PTY-KL"]
    task.blocked_since = datetime.now(timezone.utc)
    db_session.flush()
    board = list_blockers(project_id=task.project_id, session=db_session, viewer_id=org_ids["users"]["duc"])
    assert board["groups"][0]["waiting_on"]["name"] == "Xưởng Kim Long"
    assert board["groups"][0]["tasks"][0]["task_id"] == task.id
    with pytest.raises(HTTPException) as denied:
        list_blockers(project_id=task.project_id, session=db_session, viewer_id=org_ids["users"]["tuan"])
    assert denied.value.status_code == 403


def test_workspace_returns_attention_lamp_without_counting_it_as_a_blocker(db_session, org_ids):
    task = _task(db_session, org_ids, start_date=datetime.now(timezone.utc) - timedelta(days=1))
    payload = workspace(project_id=task.project_id, session=db_session, viewer_id=org_ids["users"]["duc"])
    assert payload["counts"]["blockers"] == 0
    assert {"task_id": task.id, "lamp": "late-start"} in payload["radar"]["lamps"]


def test_lead_approval_blocks_then_unblock_clears_waiting_metadata(db_session, org_ids):
    task = _task(db_session, org_ids)
    _record_signal(db_session, org_ids, task_id=task.id, message_id=8831)
    _record_signal(db_session, org_ids, task_id=task.id, message_id=8832)
    SignalsConsumer(db_session).poll_and_apply()
    decision = db_session.scalar(select(Decision).where(Decision.review_reason == "signal_promotion"))
    assert decision is not None

    # A regular member cannot approve; the owning team lead can.
    denied = DecisionsService(db_session, task_port=TasksService(db_session)).handle(ApproveProposal(
        client_command_id=uuid.uuid4(), persona="duc", created_from=CreatedFrom.DASHBOARD,
        decision_id=decision.id, approved_by_user_id=org_ids["users"]["duc"],
    ), commit=False)
    assert denied["status"] == "forbidden"
    lead = OrgService(db_session).lead_of_team(org_ids["teams"]["TEAM-EV"])
    assert lead is not None
    approved = DecisionsService(db_session, task_port=TasksService(db_session)).handle(ApproveProposal(
        client_command_id=uuid.uuid4(), persona=str(lead), created_from=CreatedFrom.DASHBOARD,
        decision_id=decision.id, approved_by_user_id=lead,
    ), commit=False)
    assert approved["status"] == "effective"
    TasksConsumer(db_session).poll_and_apply()
    db_session.flush()
    db_session.refresh(task)
    assert task.status is TaskStatus.BLOCKED
    assert task.blocked_waiting_on_party_id == org_ids["parties"]["PTY-KL"]

    update = DecisionsService(db_session, task_port=TasksService(db_session)).handle
    from evermind.contracts.commands import RecordTaskUpdate
    update(RecordTaskUpdate(client_command_id=uuid.uuid4(), persona=str(lead), created_from=CreatedFrom.DASHBOARD,
                            task_id=task.id, actor_user_id=lead, update_kind="status",
                            payload={"status": "doing"}), commit=False)
    TasksConsumer(db_session).poll_and_apply()
    db_session.flush()
    db_session.refresh(task)
    assert task.status is TaskStatus.DOING
    assert task.blocked_waiting_on_text is None and task.blocked_since is None

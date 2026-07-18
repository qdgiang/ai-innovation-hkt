"""ING-2..5 — the LLM extraction lane, hermetic (fake gateway, zero network):
window cut + cursor advance, confidence gating, failure leaves the cursor
untouched (retry next beat), re-extraction dedup, task updates, settle guard.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from evermind.connectors.models import Message
from evermind.connectors.service import ConnectorsService
from evermind.config import Settings
from evermind.ingestion.extraction import (
    ExtractedCandidate,
    ExtractionResult,
    build_user_prompt,
    candidate_unit_key,
    command_id,
)
from evermind.ingestion.models import ExtractionWindow, IngestCursor, Materialization
from evermind.ingestion.service import IngestionService
from evermind.llm.client import LLMCallResult, LLMUnavailable
from evermind.decisions.service import DecisionsService
from evermind.tasks.models import Task, TaskAssignment


class FakeGateway:
    """Stands in for llm.client.LLMGateway — same call_json shape."""

    def __init__(self, result: ExtractionResult | None = None,
                 error: Exception | None = None):
        self.result, self.error = result, error
        self.calls: list[tuple[str, str]] = []

    def call_json(self, *, system: str, user: str, schema):
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return self.result, LLMCallResult(model="fake", tokens_in=10, tokens_out=5,
                                          latency_ms=1, validation_attempts=1)


def _msg(db_session, group_id: int, mid: int, author: str, text: str,
         *, minutes_ago: int, source: str = "replay",
         author_platform_id: str | None = None,
         thread_ref: int | None = None, mentions: list[dict] | None = None) -> Message:
    captured_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    message = Message(
        id=mid, source=source, group_id=group_id, author_identity=author,
        author_platform_id=author_platform_id,
        ts=captured_at, captured_at=captured_at, text=text, thread_ref=thread_ref,
        mentions=mentions or [], raw_ref=f"test:{mid}", kind="text",
    )
    db_session.add(message)
    db_session.flush()
    return message


def test_window_extracts_and_confidence_gates(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    _msg(db_session, group_id, 9101, "duc", "Sân khấu cần 2 loa mới", minutes_ago=40)
    last = _msg(db_session, group_id, 9102, "linh",
                "Ok chốt mua 2 loa của Kim Long", minutes_ago=39)
    gateway = FakeGateway(result=ExtractionResult(candidates=[
        ExtractedCandidate(kind="decision", description="Mua 2 loa của Kim Long",
                           decided_by_message_id=9102,
                           evidence_message_ids=[9101, 9102], confidence=0.95),
        ExtractedCandidate(kind="new_task", description="Khảo sát giá loa dự phòng",
                           decided_by_message_id=9102,
                           evidence_message_ids=[9102], confidence=0.5),
    ]))

    outcome = IngestionService(db_session).run_window(group_id, gateway=gateway)

    assert outcome["status"] == "done"
    # confidence 0.95 + linh (coordinator) -> effective; 0.5 -> born proposed
    assert outcome["outcomes"][0]["status"] == "effective"
    assert outcome["outcomes"][1]["status"] == "proposed"
    assert db_session.scalar(
        select(Task).where(Task.description == "Mua 2 loa của Kim Long")) is not None
    cursor = db_session.get(IngestCursor, group_id)
    assert cursor.high_water_seq == int(last.ts.timestamp())
    window = db_session.get(ExtractionWindow, outcome["window_id"])
    assert window.status == "done" and window.tokens_in == 10
    # hydration reached the prompt
    assert "Kim Long" in gateway.calls[0][1]


def test_llm_failure_leaves_cursor_untouched_and_retries(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    _msg(db_session, group_id, 9111, "linh", "Chốt thuê rạp của trường", minutes_ago=30)

    failing = FakeGateway(error=LLMUnavailable("provider down"))
    outcome = IngestionService(db_session).run_window(group_id, gateway=failing)

    assert outcome["status"] == "llm_unavailable"
    assert db_session.get(IngestCursor, group_id) is None  # nothing acknowledged
    assert db_session.get(ExtractionWindow, outcome["window_id"]).status == "failed"

    # next beat retries the SAME messages and succeeds
    retry = FakeGateway(result=ExtractionResult(candidates=[]))
    second = IngestionService(db_session).run_window(group_id, gateway=retry)
    assert second["status"] == "done"
    assert db_session.get(IngestCursor, group_id) is not None


def test_reextraction_of_a_window_is_idempotent(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    _msg(db_session, group_id, 9121, "linh", "Chốt in 300 tờ rơi", minutes_ago=30)
    result = ExtractionResult(candidates=[
        ExtractedCandidate(kind="decision", description="In 300 tờ rơi",
                           decided_by_message_id=9121,
                           evidence_message_ids=[9121], confidence=0.9)])

    service = IngestionService(db_session)
    first = service.run_window(group_id, gateway=FakeGateway(result=result))
    assert first["outcomes"][0]["status"] == "effective"

    # cursor lost (ops mishap) -> same window re-extracted -> dedup, no twins
    cursor = db_session.get(IngestCursor, group_id)
    cursor.high_water_seq = 0
    cursor.captured_at = None
    cursor.message_id = None
    db_session.flush()
    second = service.run_window(group_id, gateway=FakeGateway(result=result))
    assert second["outcomes"][0]["status"] == "already_materialized"
    tasks = db_session.scalars(
        select(Task).where(Task.description == "In 300 tờ rơi")).all()
    assert len(tasks) == 1
    llm_rows = db_session.scalars(
        select(Materialization).where(Materialization.kind == "llm")).all()
    assert len(llm_rows) == 1


def test_task_update_candidate_moves_an_open_task(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    marker = _msg(db_session, group_id, 9131, "linh",
                  "!decision Thuê xe tải chở đèn", minutes_ago=60)
    service = IngestionService(db_session)
    service.apply_markers(marker.id)
    task = db_session.scalar(
        select(Task).where(Task.description == "Thuê xe tải chở đèn"))
    assert task is not None

    _msg(db_session, group_id, 9132, "linh", "Xe tải xong rồi nhé", minutes_ago=30)
    gateway = FakeGateway(result=ExtractionResult(candidates=[
        ExtractedCandidate(kind="task_update", description="Xe tải đã xong",
                           status="done", task_id=task.id,
                           decided_by_message_id=9132,
                           evidence_message_ids=[9132], confidence=0.9)]))
    outcome = service.run_window(group_id, gateway=gateway)

    assert outcome["outcomes"][0]["status"] == "applied"
    db_session.refresh(task)
    assert task.status.value == "done"


def test_beat_sweeps_live_platform_groups_only(db_session, org_ids):
    """The scheduler beat must never LLM-extract the seeded replay corpus —
    only groups on live-connector platforms (identity.ADAPTERS)."""
    corpus_gid = org_ids["groups"]["G-TT"]
    live_gid = org_ids["groups"]["G-4AE"]
    _msg(db_session, corpus_gid, 9151, "linh",
         "Corpus không được tự động extract", minutes_ago=30)
    _msg(db_session, live_gid, 9152, "pqminh", "Chốt mua 100 bánh trung thu",
         minutes_ago=30, source="telegram", author_platform_id="1210670436")
    gateway = FakeGateway(result=ExtractionResult(candidates=[]))

    results = IngestionService(db_session).run_pending_windows(gateway=gateway)

    assert [r["group_id"] for r in results] == [live_gid]
    assert db_session.get(IngestCursor, corpus_gid) is None


def test_settle_guard_never_cuts_an_active_conversation(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    _msg(db_session, group_id, 9141, "linh", "Đang bàn tiếp nè", minutes_ago=0)
    gateway = FakeGateway(result=ExtractionResult(candidates=[]))

    outcome = IngestionService(db_session).run_window(group_id, gateway=gateway)

    assert outcome["status"] == "settling"
    assert gateway.calls == []  # no LLM spend on a still-flowing chat
    assert db_session.get(IngestCursor, group_id) is None
    assert db_session.scalars(select(ExtractionWindow)).all() == []


def test_prompt_marks_pending_and_cite_only_reply_context():
    """Historic reply parents are evidence-only, never extraction anchors."""
    parent = Message(
        id=9901, source="telegram", group_id=1, author_identity="linh",
        author_platform_id="1", ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
        text="Chốt thuê rạp", thread_ref=None, raw_ref="test:9901", kind="text",
    )
    pending = Message(
        id=9902, source="telegram", group_id=1, author_identity="duc",
        author_platform_id="2", ts=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        text="Ok chốt", thread_ref=9901, raw_ref="test:9902", kind="text",
    )

    prompt = build_user_prompt(
        [pending], context_messages=[parent], members=[], open_tasks=[], parties=[]
    )

    assert "PENDING — có thể làm anchor" in prompt
    assert "CITE-ONLY — không được làm anchor" in prompt
    assert "reply_to=9901" in prompt
    assert "[9901]" in prompt and "[9902]" in prompt


def test_task_assignment_candidate_carries_allowed_assignee_ids():
    candidate = ExtractedCandidate(
        kind="task_assignment", description="Giao việc", task_id=42,
        assignee_user_ids=[7, 8], decided_by_message_id=1,
        evidence_message_ids=[1], confidence=0.9,
    )

    assert candidate.assignee_user_ids == [7, 8]


def test_extraction_max_wait_cannot_be_less_than_settle():
    with pytest.raises(ValidationError):
        Settings(extraction_settle_sec=15, extraction_max_wait_sec=14)


@pytest.mark.parametrize("kwargs", [
    {"extraction_interval_sec": -1},
    {"extraction_settle_sec": -1},
    {"extraction_max_wait_sec": -1},
])
def test_extraction_times_are_nonnegative(kwargs):
    with pytest.raises(ValidationError):
        Settings(**kwargs)


def test_marker_only_window_advances_capture_cursor(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    marker = _msg(db_session, group_id, 9201, "linh", "!decision already handled", minutes_ago=5)

    first = IngestionService(db_session).run_window(group_id, gateway=FakeGateway())

    cursor = db_session.get(IngestCursor, group_id)
    assert first["status"] == "empty_window"
    assert cursor.message_id == marker.id

    next_message = _msg(db_session, group_id, 9202, "linh", "Chốt việc tiếp theo", minutes_ago=4)
    gateway = FakeGateway(result=ExtractionResult(candidates=[]))
    second = IngestionService(db_session).run_window(group_id, gateway=gateway)

    assert second["status"] == "done"
    assert len(gateway.calls) == 1
    assert db_session.get(IngestCursor, group_id).message_id == next_message.id


def test_hydration_follows_two_hops_when_parent_is_in_history_tail(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    grandparent = _msg(db_session, group_id, 9301, "linh", "Original task", minutes_ago=30)
    parent = _msg(db_session, group_id, 9302, "duc", "Reply to task", minutes_ago=20,
                  thread_ref=grandparent.id)
    pending = _msg(db_session, group_id, 9303, "linh", "Confirmed", minutes_ago=10,
                   thread_ref=parent.id)

    context = ConnectorsService(db_session).hydrate_context(group_id, [pending])

    assert {message.id for message in context} >= {parent.id, grandparent.id}


def test_candidate_units_and_command_ids_do_not_collide():
    update = ExtractedCandidate(kind="task_update", description="done", status="done", task_id=7,
                                decided_by_message_id=1, evidence_message_ids=[1], confidence=0.9)
    assignment_a = ExtractedCandidate(kind="task_assignment", description="assign", task_id=7,
                                      assignee_user_ids=[2], decided_by_message_id=1,
                                      evidence_message_ids=[1], confidence=0.9)
    assignment_b = assignment_a.model_copy(update={"assignee_user_ids": [3]})

    keys = {candidate_unit_key(candidate) for candidate in (update, assignment_a, assignment_b)}
    assert len(keys) == 3
    assert command_id(1, 10, 100, "first") != command_id(1, 11, 100, "first")


def test_assignment_schema_rejects_non_assignment_kinds():
    with pytest.raises(ValidationError):
        ExtractedCandidate(kind="decision", description="decision", assignee_user_ids=[1],
                           decided_by_message_id=1, evidence_message_ids=[1], confidence=0.9)
    with pytest.raises(ValidationError):
        ExtractedCandidate(kind="new_task", description="task", self_assignment=True,
                           decided_by_message_id=1, evidence_message_ids=[1], confidence=0.9)


def test_invalid_task_id_is_recorded_without_entering_gateway(db_session, org_ids):
    group_id = org_ids["groups"]["G-TT"]
    message = _msg(db_session, group_id, 9501, "linh", "Đánh dấu xong", minutes_ago=5)
    gateway = FakeGateway(result=ExtractionResult(candidates=[
        ExtractedCandidate(kind="task_update", description="invalid target", status="done", task_id=999999,
                           decided_by_message_id=message.id, evidence_message_ids=[message.id], confidence=0.95),
    ]))

    outcome = IngestionService(db_session).run_window(group_id, gateway=gateway)

    assert outcome["outcomes"][0]["status"] == "invalid_task_id"
    assert db_session.get(IngestCursor, group_id).message_id == message.id


def test_duplicate_candidates_in_one_window_materialize_once_with_autoflush_disabled(
    db_session, org_ids,
):
    db_session.commit()
    group_id = org_ids["groups"]["G-TT"]
    with Session(db_session.get_bind(), autoflush=False, expire_on_commit=False) as prod_session:
        message = _msg(prod_session, group_id, 9502, "linh", "Chốt việc trùng", minutes_ago=5)
        candidate = ExtractedCandidate(kind="new_task", description="Việc chỉ một lần",
                                       decided_by_message_id=message.id,
                                       evidence_message_ids=[message.id], confidence=0.95)
        outcome = IngestionService(prod_session).run_window(
            group_id, gateway=FakeGateway(result=ExtractionResult(candidates=[candidate, candidate])))

        assert [item["status"] for item in outcome["outcomes"]] == ["effective", "duplicate_in_window"]
        assert len(prod_session.scalars(select(Task).where(Task.description == "Việc chỉ một lần")).all()) == 1


def test_crashed_candidate_does_not_block_remaining_window_or_cursor(db_session, org_ids, monkeypatch):
    group_id = org_ids["groups"]["G-TT"]
    message = _msg(db_session, group_id, 9503, "linh", "Chốt hai việc", minutes_ago=5)
    original_handle = DecisionsService.handle

    def crash_only_first(self, command, **kwargs):
        if command.description == "broken":
            raise RuntimeError("simulated gateway bug")
        return original_handle(self, command, **kwargs)

    monkeypatch.setattr(DecisionsService, "handle", crash_only_first)
    outcome = IngestionService(db_session).run_window(group_id, gateway=FakeGateway(result=ExtractionResult(candidates=[
        ExtractedCandidate(kind="new_task", description="broken", decided_by_message_id=message.id,
                           evidence_message_ids=[message.id], confidence=0.95),
        ExtractedCandidate(kind="new_task", description="survives", decided_by_message_id=message.id,
                           evidence_message_ids=[message.id], confidence=0.95),
    ])))

    assert [item["status"] for item in outcome["outcomes"]] == ["candidate_crashed", "effective"]
    assert db_session.get(IngestCursor, group_id).message_id == message.id
    assert db_session.scalar(select(Task).where(Task.description == "survives")) is not None


def test_self_assignment_projects_to_existing_task_assignment_with_production_autoflush(
    db_session, org_ids,
):
    """Telegram anchor -> explicit self assignment -> task projection with prod session semantics."""
    db_session.commit()
    group_id = org_ids["groups"]["G-4AE"]
    actor_id = org_ids["users"]["minhpq"]
    with Session(db_session.get_bind(), autoflush=False, expire_on_commit=False) as prod_session:
        message = _msg(prod_session, group_id, 9401, "pqminh", "Tôi sẽ lo phần này", minutes_ago=5,
                       source="telegram", author_platform_id="1210670436")
        gateway = FakeGateway(result=ExtractionResult(candidates=[
            ExtractedCandidate(kind="new_task", description="Lo phần này", assignee_user_ids=[actor_id],
                               self_assignment=True, decided_by_message_id=message.id,
                               evidence_message_ids=[message.id], confidence=0.95),
        ]))

        outcome = IngestionService(prod_session).run_window(group_id, gateway=gateway)

        assert outcome["outcomes"][0]["status"] == "effective"
        task = prod_session.scalar(select(Task).where(Task.description == "Lo phần này"))
        assert task is not None
        assert prod_session.get(TaskAssignment, {"task_id": task.id, "user_id": actor_id}) is not None

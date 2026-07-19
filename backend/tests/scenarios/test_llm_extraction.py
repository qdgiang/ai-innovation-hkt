"""ING-2..5 — the LLM extraction lane, hermetic (fake gateway, zero network):
window cut + cursor advance, confidence gating, failure leaves the cursor
untouched (retry next beat), re-extraction dedup, task updates, settle guard.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from evermind.connectors.models import Message
from evermind.ingestion.extraction import ExtractedCandidate, ExtractionResult
from evermind.ingestion.models import ExtractionWindow, IngestCursor, Materialization
from evermind.ingestion.service import IngestionService
from evermind.llm.client import LLMCallResult, LLMUnavailable
from evermind.tasks.models import Task


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
         author_platform_id: str | None = None) -> Message:
    message = Message(
        id=mid, source=source, group_id=group_id, author_identity=author,
        author_platform_id=author_platform_id,
        ts=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        text=text, thread_ref=None, raw_ref=f"test:{mid}", kind="text",
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
    db_session.get(IngestCursor, group_id).high_water_seq = 0
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


def test_window_emits_weak_signals_to_ledger(db_session, org_ids):
    """SIG-1 producer half: extraction drafts weak signals -> RecordSignal
    through the gateway -> signal_recorded event -> ledger row, with the party
    resolved via org aliases (SIG-2) and the author identity attached."""
    from evermind.ingestion.extraction import ExtractedSignal
    from evermind.signals.consumer import SignalsConsumer
    from evermind.signals.models import Signal

    group_id = org_ids["groups"]["G-TT"]
    _msg(db_session, group_id, 9301, "duc",
         "bên Kim Long vẫn chưa báo giá backdrop", minutes_ago=30)
    gateway = FakeGateway(result=ExtractionResult(candidates=[], signals=[
        ExtractedSignal(kind="blocker", topic="Kim Long chưa báo giá",
                        excerpt="vẫn chưa báo giá", message_id=9301,
                        party="Kim Long"),
    ]))

    outcome = IngestionService(db_session).run_window(group_id, gateway=gateway)

    assert outcome["status"] == "done"
    assert outcome["signals"][0]["status"] == "signal_recorded"
    assert outcome["signals"][0]["party_id"] == org_ids["parties"]["PTY-KL"]

    SignalsConsumer(db_session).poll_and_apply()
    signal = db_session.scalar(select(Signal))
    assert signal is not None
    assert signal.normalized_topic == "kim long chưa báo giá"
    assert signal.party_id == org_ids["parties"]["PTY-KL"]
    assert signal.reported_by_user_id == org_ids["users"]["duc"]
    assert signal.message_id == 9301


def test_hallucinated_signal_message_id_is_dropped(db_session, org_ids):
    from evermind.ingestion.extraction import ExtractedSignal
    from evermind.signals.models import Signal

    group_id = org_ids["groups"]["G-TT"]
    _msg(db_session, group_id, 9401, "duc", "cập nhật tiến độ nhẹ", minutes_ago=30)
    gateway = FakeGateway(result=ExtractionResult(candidates=[], signals=[
        ExtractedSignal(kind="blocker", topic="ma", excerpt="x", message_id=4242),
    ]))

    outcome = IngestionService(db_session).run_window(group_id, gateway=gateway)

    assert outcome["signals"][0]["status"] == "hallucinated_message_id"
    assert db_session.scalar(select(Signal)) is None

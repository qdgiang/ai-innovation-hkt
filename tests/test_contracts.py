"""Every contract rule in ai-docs/features.md gets asserted here."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from ai.schemas import (
    BlockerBody,
    Citation,
    CreatedFrom,
    DecisionBody,
    ExtractedRecord,
    Message,
    Record,
    RecordStatus,
    RecordType,
    Source,
)
from backend.app.models import Base, RecordSourceRow
from backend.app.repository import CitationRequiredError, save_message, save_record

TS = dt.datetime(2026, 6, 10, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=7)))


def make_message(**overrides) -> Message:
    base = dict(
        id="m0001",
        source=Source.REPLAY,
        channel="aiv-events",
        team="events",
        author="linh",
        ts=TS,
        text="fair venue = community center, ok?",
        raw_ref="corpus.jsonl:1",
    )
    base.update(overrides)
    return Message(**base)


def make_record(**overrides) -> Record:
    base = dict(
        id="r-001",
        type=RecordType.DECISION,
        title="Fair venue: Phuong Liet Community Center",
        body=DecisionBody(summary="Venue chosen", decided_by="linh"),
        team="events",
        created_from=CreatedFrom.LLM,
        confidence=0.9,
    )
    base.update(overrides)
    return Record(**base)


class TestMessage:
    def test_roundtrip(self):
        msg = make_message()
        assert Message.model_validate_json(msg.model_dump_json()) == msg

    def test_naive_timestamp_rejected(self):
        with pytest.raises(ValidationError):
            make_message(ts=dt.datetime(2026, 6, 10, 9, 0))

    def test_raw_ref_required(self):
        with pytest.raises(ValidationError):
            Message(
                id="m1", source="replay", channel="c", author="a", ts=TS, text="hi"
            )

    def test_team_and_thread_ref_optional(self):
        msg = make_message(team=None, thread_ref=None)
        assert msg.team is None and msg.thread_ref is None

    def test_frozen(self):
        with pytest.raises(ValidationError):
            make_message().text = "edited"


class TestRecord:
    def test_status_defaults_active(self):
        assert make_record().status is RecordStatus.ACTIVE

    def test_body_kind_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            make_record(body=BlockerBody(waiting_on="sound guy"))

    def test_body_dict_kind_inferred_from_type(self):
        rec = Record(
            id="r-002",
            type="blocker",
            title="Sound supplier unresponsive",
            body={"waiting_on": "sound rental supplier", "owner": "duc"},
            team="events",
            created_from="llm",
            confidence=0.7,
        )
        assert isinstance(rec.body, BlockerBody)

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_confidence_bounds(self, confidence):
        with pytest.raises(ValidationError):
            make_record(confidence=confidence)

    def test_invalid_lifecycle_status_rejected(self):
        with pytest.raises(ValidationError):
            make_record(status="archived")


class TestCitationRule:
    def test_extracted_record_requires_citation(self):
        with pytest.raises(ValidationError):
            ExtractedRecord(record=make_record(), citation_message_ids=[])

    def test_citation_model(self):
        c = Citation(record_id="r-001", message_id="m0001")
        assert (c.record_id, c.message_id) == ("r-001", "m0001")


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class TestPersistence:
    def test_record_without_citation_fails(self, session):
        with pytest.raises(CitationRequiredError):
            save_record(session, make_record(), citation_message_ids=[])

    def test_record_with_citation_persists(self, session):
        save_message(session, make_message())
        save_record(session, make_record(), citation_message_ids=["m0001"])
        session.commit()
        count = session.execute(select(func.count(RecordSourceRow.record_id))).scalar_one()
        assert count == 1

    def test_duplicate_citations_deduped(self, session):
        save_message(session, make_message())
        save_record(session, make_record(), citation_message_ids=["m0001", "m0001"])
        session.commit()
        count = session.execute(select(func.count(RecordSourceRow.record_id))).scalar_one()
        assert count == 1

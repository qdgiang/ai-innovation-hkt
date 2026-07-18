"""L1 — CAP-2 replay connector (plan.md P2 Lane B)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message
from evermind.connectors.replay import ReplayConnector

DATA_V2 = Path(__file__).resolve().parents[3] / "data-v2"
CHANNEL_GROUP_IDS = {"aiv-trungthu": 1, "aiv-classes": 2}


def test_replay_ingests_the_whole_corpus_in_order(db_session: Session):
    count = ReplayConnector(db_session).replay(
        DATA_V2 / "corpus.jsonl", channel_group_ids=CHANNEL_GROUP_IDS, pace_ms=0,
    )
    assert count == 118  # data-v2/README.md: TT 89 + CL 29

    first = db_session.get(Message, 1)
    assert first is not None
    assert first.author_identity == "linh"
    assert first.group_id == 1
    assert first.raw_ref == "corpus.jsonl:1"

    photo = db_session.get(Message, 100)
    assert photo.kind == "photo"
    assert photo.author_identity == "minh"


def test_replay_is_idempotent_on_rerun(db_session: Session):
    first_run = ReplayConnector(db_session).replay(
        DATA_V2 / "corpus.jsonl", channel_group_ids=CHANNEL_GROUP_IDS,
    )
    second_run = ReplayConnector(db_session).replay(
        DATA_V2 / "corpus.jsonl", channel_group_ids=CHANNEL_GROUP_IDS,
    )
    assert first_run == 118
    assert second_run == 0
    all_messages = db_session.scalars(select(Message)).all()
    assert len(all_messages) == 118  # not duplicated


def test_replay_resolves_thread_ref_to_message_id(db_session: Session):
    ReplayConnector(db_session).replay(
        DATA_V2 / "corpus.jsonl", channel_group_ids=CHANNEL_GROUP_IDS,
    )
    threaded = db_session.scalars(
        select(Message).where(Message.thread_ref.is_not(None))
    ).first()
    assert threaded is not None
    assert isinstance(threaded.thread_ref, int)

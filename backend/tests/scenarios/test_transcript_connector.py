"""L1 — CAP-3 transcript connector (plan.md P3 Lane B)."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message, SpeakerMap, Upload
from evermind.connectors.replay import ReplayConnector
from evermind.connectors.transcript import TranscriptConnector, UnsupportedTranscriptType

DATA_V2 = Path(__file__).resolve().parents[3] / "data-v2"
TRANSCRIPT = DATA_V2 / "meeting-2026-09-07.txt"


def test_upload_parses_all_turns_as_messages(db_session: Session):
    upload_id = TranscriptConnector(db_session).upload(
        filename="meeting-2026-09-07.txt", content=TRANSCRIPT.read_text(encoding="utf-8"),
        uploaded_by=1,
    )
    upload = db_session.get(Upload, upload_id)
    assert upload is not None
    assert upload.version == 1

    turns = db_session.scalars(
        select(Message).where(Message.source == "transcript")
    ).all()
    assert len(turns) == 38  # pinned by test_fixtures_l0.py::test_transcript_shape
    assert {t.author_identity for t in turns} >= {"Linh", "Mai", "Duc", "Khoa", "An", "Huong"}


def test_speaker_map_seeded_unmapped(db_session: Session):
    upload_id = TranscriptConnector(db_session).upload(
        filename="meeting-2026-09-07.txt", content=TRANSCRIPT.read_text(encoding="utf-8"),
        uploaded_by=1,
    )
    speakers = db_session.scalars(
        select(SpeakerMap).where(SpeakerMap.upload_id == upload_id)
    ).all()
    names = {s.display_name for s in speakers}
    assert "Linh" in names
    assert all(s.user_id is None for s in speakers)  # G30: unmapped until confirmed


def test_confirm_speaker_resolves_a_display_name(db_session: Session):
    connector = TranscriptConnector(db_session)
    upload_id = connector.upload(
        filename="meeting-2026-09-07.txt", content=TRANSCRIPT.read_text(encoding="utf-8"),
        uploaded_by=1,
    )
    connector.confirm_speaker(upload_id, "Linh", user_id=42)
    row = db_session.scalars(
        select(SpeakerMap)
        .where(SpeakerMap.upload_id == upload_id)
        .where(SpeakerMap.display_name == "Linh")
    ).first()
    assert row.user_id == 42


def test_reupload_creates_a_new_version_never_overwrites(db_session: Session):
    connector = TranscriptConnector(db_session)
    first = connector.upload(
        filename="meeting-2026-09-07.txt", content=TRANSCRIPT.read_text(encoding="utf-8"),
        uploaded_by=1,
    )
    second = connector.upload(
        filename="meeting-2026-09-07.txt", content=TRANSCRIPT.read_text(encoding="utf-8"),
        uploaded_by=1,
    )
    assert db_session.get(Upload, first).version == 1
    assert db_session.get(Upload, second).version == 2
    assert first != second

    all_turns = db_session.scalars(select(Message).where(Message.source == "transcript")).all()
    assert len(all_turns) == 76  # both uploads' turns coexist (re-upload ≠ overwrite)


def test_upload_rejects_non_txt_md(db_session: Session):
    """[EVM-011] txt/md only — the gate is server-side, not just the FE's
    file-picker `accept` hint."""
    with pytest.raises(UnsupportedTranscriptType):
        TranscriptConnector(db_session).upload(
            filename="meeting-2026-09-07.pdf", content="[00:01] Linh: hi", uploaded_by=1,
        )
    assert db_session.scalars(select(Upload)).first() is None  # nothing half-written


def test_upload_accepts_md(db_session: Session):
    upload_id = TranscriptConnector(db_session).upload(
        filename="meeting-2026-09-07.md", content="[00:01] Linh: hi", uploaded_by=1,
    )
    assert db_session.get(Upload, upload_id) is not None


def test_transcript_and_replay_message_ids_never_collide(db_session: Session):
    replay_count = ReplayConnector(db_session).replay(
        DATA_V2 / "corpus.jsonl", channel_group_ids={"aiv-trungthu": 1, "aiv-classes": 2},
    )
    TranscriptConnector(db_session).upload(
        filename="meeting-2026-09-07.txt", content=TRANSCRIPT.read_text(encoding="utf-8"),
        uploaded_by=1,
    )
    all_ids = [m.id for m in db_session.scalars(select(Message)).all()]
    assert len(all_ids) == len(set(all_ids))  # no PK collision
    assert replay_count == 118

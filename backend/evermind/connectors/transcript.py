"""Owner: B. CAP-3 — transcript upload connector: `[MM:SS] Name: text` parsing +
attendee header; `.txt`/`.md` only [EVM-011]. Speaker map auto-seeded from
`users.name`, confirmable at upload (G30) — resolution itself is A's (interface #7).
STUB — P3 deliverable.
"""
from __future__ import annotations

from sqlalchemy.orm import Session


class TranscriptConnector:
    def __init__(self, session: Session):
        self.session = session

    def upload(self, *, filename: str, content: str, uploaded_by: int) -> int:
        """TODO(B): create an `ingestion.models.Upload` row (version = N+1 if filename
        seen before — never overwrite), parse turns into Message rows (source=
        "transcript"), seed `speaker_maps` from display names. Then call
        `ingestion.service.IngestionService.on_transcript_uploaded` (interface #7:
        A resolves speaker maps + flushes the window). Returns the upload id.
        """
        raise NotImplementedError

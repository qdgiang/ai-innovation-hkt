"""Owner: B. CAP-2 — replay connector: feeds data-v2/corpus.jsonl through the
same path as live capture. Instant mode (tests, REPLAY_PACE_MS=0) and paced
mode (demo beat). STUB — P2 deliverable.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session


class ReplayConnector:
    def __init__(self, session: Session):
        self.session = session

    def replay(self, corpus_path: Path, pace_ms: int = 0) -> int:
        """TODO(B): parse corpus.jsonl lines -> Message rows (source="replay"),
        respecting global time order; `pace_ms` sleeps between inserts for the
        demo beat. Returns count of messages ingested.
        """
        raise NotImplementedError

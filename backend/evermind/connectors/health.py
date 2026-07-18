"""Owner: B. CAP-5 (T2) — capture health monitoring: bot-membership loss ->
coordinator feed alert + dashboard banner (G53). STUB — P6 deliverable.
"""
from __future__ import annotations

from sqlalchemy.orm import Session


class CaptureHealthService:
    def __init__(self, session: Session):
        self.session = session

    def check_all_groups(self) -> list[dict]:
        """TODO(B): daily self-check per mapped group; a severed feed is never
        presented as a quiet week — emits a `surfacing` feed entry + `/health/capture`
        banner data on loss.
        """
        raise NotImplementedError

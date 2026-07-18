"""Owner: A. Windows, markers, hydration, extraction, linkage, signals-emit.

STUB — P2/P3 deliverable (ING-1..8). Emits `contracts.commands` only; never
writes decisions/tasks/signals tables directly.
"""
from __future__ import annotations

from sqlalchemy.orm import Session


class IngestionService:
    def __init__(self, session: Session):
        self.session = session

    def run_window(self, group_id: int) -> None:
        """TODO(A): ING-2 windowing + ING-3 hydration + ING-4 extraction + ING-5 linkage.
        Reads messages via `connectors.service.ConnectorsService.read_window` (B's read
        port — work-split.md interface #1), never `connectors.models` directly.
        """
        raise NotImplementedError

    def apply_markers(self, message_id: int) -> None:
        """TODO(A): ING-1 — deterministic grammar, instant, confidence 1.0."""
        raise NotImplementedError

    def on_transcript_uploaded(self, upload_id: int) -> None:
        """TODO(A): interface #7 (work-split.md) — B parses+stores the upload
        (`connectors`/CAP-3); A resolves speaker maps + flushes the window here.
        """
        raise NotImplementedError

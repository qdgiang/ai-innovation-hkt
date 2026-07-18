"""Owner: B. Ledger, promotion, radar lamps, overload, escalation
(SIG-1..5, plan.md P2/P3/P4)."""
from __future__ import annotations

from sqlalchemy.orm import Session


class SignalsService:
    def __init__(self, session: Session):
        self.session = session

    def emit(self, *, kind: str, project_id: int, normalized_topic: str, excerpt: str,
              message_id: int, window_id: int, task_id: int | None = None,
              party_id: int | None = None) -> int:
        """TODO(B): SIG-1 — append-only ledger row keyed on the [EVM-013] identity;
        does NOT auto-promote. Returns the signal id."""
        raise NotImplementedError

    def try_promote(self, project_id: int, normalized_topic: str) -> None:
        """TODO(B): SIG-1 promotion — >=2 corroborating signals, or 1 + staleness,
        emits a `RecordSignal`/proposed-blocked command via `decisions.service`
        (never writes tasks.blocked_* directly)."""
        raise NotImplementedError

    def radar_sweep(self) -> list[dict]:
        """TODO(B): SIG-3 daily job — flush-before-read, then lamps: blocked/at-risk/
        overdue/stale/idle/late-start/contested. Reads `tasks.service` (read port)."""
        raise NotImplementedError

    def overload_for(self, user_id: int) -> dict:
        """TODO(B): SIG-4 — per-day concurrent load, next 14 days, warn-don't-block."""
        raise NotImplementedError

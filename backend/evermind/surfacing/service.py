"""Owner: B. Feed, inbox, digest, close-out, on/offboarding
(SRF-1..6, plan.md P4/P6)."""
from __future__ import annotations

from sqlalchemy.orm import Session


class SurfacingService:
    def __init__(self, session: Session):
        self.session = session

    def feed_for(self, persona_user_id: int) -> list[dict]:
        """TODO(B): SRF-1 — batched (~30min), deduped feed entries for this persona."""
        raise NotImplementedError

    def inbox_for(self, persona_user_id: int) -> list[dict]:
        """TODO(B): SRF-2 — proposals/confirms/challenges/diffs/triage + capture receipts."""
        raise NotImplementedError

    def digest_for(self, team_id: int, week: str) -> dict:
        """TODO(B): SRF-3 — decisions/tasks/blockers/pendings/needs-attention +
        project-wide section (G48) + verbatim wrap-note quote."""
        raise NotImplementedError

    def close_out(self, project_id: int) -> dict:
        """TODO(B): SRF-4 — retrospective digest on project close (G41)."""
        raise NotImplementedError

    def onboarding_brief(self, user_id: int) -> dict:
        """TODO(B): SRF-5 — filtered read: active work, decisions shaping it, blockers."""
        raise NotImplementedError

    def offboarding_sweep(self, user_id: int) -> dict:
        """TODO(B): SRF-6 — everything the departing volunteer holds, before it's lost."""
        raise NotImplementedError

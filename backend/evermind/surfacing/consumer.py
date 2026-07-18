"""Owner: B. Surfacing's event-consumer loop — folds decision-lifecycle
`domain_events` into the feed (SRF-1) and inbox (SRF-2) projections, exactly
like `tasks/consumer.py` folds them into the board. Tracks its own position
via `ProjectionOffset` (consumer="surfacing").

Routing (design-v2.md §Notifications):
  decision_proposed            -> inbox item per approver (the acting surface)
  decision_effective           -> feed entry for maker/approver/newly-assigned PICs;
                                  resolves the proposal's open inbox items
  decision_rejected            -> feed entry for the notified author (G11/G12
                                  sweep) and resolution of open inbox items
  task_update_pending_confirm  -> inbox confirm card per PIC (G9)
  challenge_filed              -> inbox item for the maker who resolves it (G18)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.db.eventlog import DomainEvent, ProjectionOffset
from evermind.surfacing.models import InboxItem
from evermind.surfacing.service import SurfacingService

CONSUMER_NAME = "surfacing"


class SurfacingConsumer:
    def __init__(self, session: Session):
        self.session = session
        self.service = SurfacingService(session)

    def _offset(self) -> ProjectionOffset:
        offset = self.session.get(ProjectionOffset, CONSUMER_NAME)
        if offset is None:
            offset = ProjectionOffset(consumer=CONSUMER_NAME, last_seq=0)
            self.session.add(offset)
            self.session.flush()
        return offset

    def poll_and_apply(self) -> int:
        offset = self._offset()
        events = self.session.scalars(
            select(DomainEvent)
            .where(DomainEvent.seq > offset.last_seq)
            .order_by(DomainEvent.seq)
        ).all()
        for event in events:
            handler = getattr(self, f"_on_{event.kind}", None)
            if handler is not None:
                handler(event)
            offset.last_seq = event.seq
        return len(events)

    # ── helpers ──────────────────────────────────────────────────────────

    def _resolve_proposal_items(self, decision_id: int, resolution: str) -> None:
        rows = self.session.scalars(
            select(InboxItem).where(
                InboxItem.kind == "proposal",
                InboxItem.ref_id == decision_id,
                InboxItem.resolved_at.is_(None),
            )
        )
        for item in rows:
            self.service.resolve_inbox_item(
                item.id, resolution=resolution,
                resolved_at=datetime.now(timezone.utc),
            )


    def _feed(self, event: DomainEvent, persona_user_id: int, kind: str,
              payload: dict) -> None:
        self.service.add_feed_entry(
            persona_user_id=persona_user_id, kind=kind, payload=payload,
            batch_key=f"{kind}:{event.aggregate}:{event.aggregate_id}",
            ts=event.ts, decision_id=event.aggregate_id if event.aggregate == "decision" else None,
            task_id=payload.get("task_id") or payload.get("new_task_id"),
        )

    # ── handlers ─────────────────────────────────────────────────────────

    def _on_decision_proposed(self, event: DomainEvent) -> None:
        decision_id = event.payload["decision_id"]
        for approver in event.payload.get("approvers") or []:
            already = self.session.scalar(select(InboxItem).where(
                InboxItem.persona_user_id == approver,
                InboxItem.kind == "proposal", InboxItem.ref_id == decision_id))
            if already is None:
                self.service.add_inbox_item(persona_user_id=approver, kind="proposal",
                                            ref_id=decision_id, created_at=event.ts)

    def _on_decision_effective(self, event: DomainEvent) -> None:
        payload = event.payload
        self._resolve_proposal_items(payload["decision_id"], "approved")
        recipients = {payload.get("decided_by_user_id"), payload.get("approved_by")}
        for op in payload.get("ops") or []:
            # newly-assigned PICs learn about work landing on them
            if op.get("facet") == "assignment":
                value = op.get("value")
                for user_id in (value if isinstance(value, list) else [value]):
                    if isinstance(user_id, int):
                        recipients.add(user_id)
        for user_id in recipients:
            if isinstance(user_id, int):
                self._feed(event, user_id, "decision_effective", {
                    "decision_id": payload["decision_id"],
                    "description": payload.get("description"),
                    "new_task_id": payload.get("new_task_id"),
                    "windowed": payload.get("windowed", False),
                })

    def _on_decision_rejected(self, event: DomainEvent) -> None:
        payload = event.payload
        self._resolve_proposal_items(payload["decision_id"], "rejected")
        notify = payload.get("notify_user_id") or payload.get("by")
        if isinstance(notify, int):
            self._feed(event, notify, "decision_rejected", {
                "decision_id": payload["decision_id"],
                "rejected_reason": payload.get("rejected_reason"),
                "superseded_by": payload.get("superseded_by"),
                "retraction": payload.get("retraction", False),
            })

    def _on_task_update_pending_confirm(self, event: DomainEvent) -> None:
        for confirmer in event.payload.get("confirmers") or []:
            self.service.add_inbox_item(persona_user_id=confirmer, kind="confirm",
                                        ref_id=event.payload["task_id"],
                                        created_at=event.ts)

    def _on_challenge_filed(self, event: DomainEvent) -> None:
        resolver = event.payload.get("resolves_to")
        if isinstance(resolver, int):
            self.service.add_inbox_item(persona_user_id=resolver, kind="challenge",
                                        ref_id=event.payload["decision_id"],
                                        created_at=event.ts)

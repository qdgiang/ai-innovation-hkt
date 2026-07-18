"""Owner: B. The event-consumer loop — D3 read side. `decisions` (A) appends
`domain_events`; this module folds them into the `tasks` projection and never
writes anything else. Tracks its own position via
`evermind.db.eventlog.ProjectionOffset` (consumer="tasks").

P1: tested against a synthetic `domain_events` stream until A's gateway lands
(plan.md P1 Lane B note) — see `backend/tests/scenarios/test_tasks_fold.py`.

Event payload shapes assumed (pending A's real contract-first PR):
  decision_effective:    {"decision_id": int, "ops": [{"target","facet","op","value"}, ...]}
  task_update_recorded:  {"task_id": int, "actor_user_id": int, "kind": "status"|"note",
                          "payload": {...}, "created_from": str, "confidence": float|None,
                          "source_message_id": int|None}
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import TaskStatus
from evermind.db.eventlog import DomainEvent, ProjectionOffset
from evermind.tasks import dependencies, fold
from evermind.tasks.models import Task, TaskDecisionLog, TaskUpdate

CONSUMER_NAME = "tasks"


class TasksConsumer:
    def __init__(self, session: Session):
        self.session = session

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
            self._apply_event(event)
            offset.last_seq = event.seq
        return len(events)

    def _apply_event(self, event: DomainEvent) -> None:
        handler = getattr(self, f"_on_{event.kind}", None)
        if handler is None:
            return  # events this projection doesn't care about (e.g. signal_*)
        handler(event)

    def _on_decision_effective(self, event: DomainEvent) -> None:
        decision_id = event.payload["decision_id"]
        ops = event.payload["ops"]
        touched_task_ids = fold.apply_decision_ops(self.session, decision_id=decision_id, ops=ops)
        for task_id in set(touched_task_ids):
            self.session.add(TaskDecisionLog(
                task_id=task_id, decision_id=decision_id, ts=event.ts,
                recorded_at=event.ts, stable_event_id=event.caused_by_command, ops=ops,
            ))
            task = self.session.get(Task, task_id)
            if task is not None and task.status == TaskStatus.CANCELED:
                dependencies.on_predecessor_status_changed(self.session, predecessor_id=task_id)

    def _on_decision_rejected(self, event: DomainEvent) -> None:
        """DEC-6: a decision that was once effective and is now vetoed stops
        counting toward the fold/time-travel replay (see TaskDecisionLog's
        `retracted` docstring for the known dual-stamp simplification).
        """
        decision_id = event.payload["decision_id"]
        rows = self.session.scalars(
            select(TaskDecisionLog).where(TaskDecisionLog.decision_id == decision_id)
        )
        for row in rows:
            row.retracted = True

    def _on_task_update_recorded(self, event: DomainEvent) -> None:
        payload = event.payload
        update = TaskUpdate(
            ts=event.ts, recorded_at=event.ts, task_id=payload["task_id"],
            actor_user_id=payload["actor_user_id"], kind=payload["kind"],
            payload=payload["payload"], created_from=payload["created_from"],
            confidence=payload.get("confidence"), source_message_id=payload.get("source_message_id"),
        )
        self.session.add(update)

        # G7: PIC auto-apply — only status-kind updates move `tasks.status`;
        # notes never do. Terminal locks (TSK-6) already kept this update from
        # being emitted for a canceled/merged task (decisions.service's job).
        if payload["kind"] == "status":
            task = self.session.get(Task, payload["task_id"])
            if task is not None:
                task.status = TaskStatus(payload["payload"]["status"])
                if task.status == TaskStatus.CANCELED:
                    dependencies.on_predecessor_status_changed(
                        self.session, predecessor_id=task.id
                    )

"""Fold signal events and submit eligible blocker promotions through the gateway."""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.commands import CitationSpec, OpSpec, ProposeDecision
from evermind.contracts.enums import (
    CitationKind,
    CreatedFrom,
    DecisionScope,
    SignalKind,
    SignalStatus,
)
from evermind.db.eventlog import DomainEvent, ProjectionOffset
from evermind.decisions.service import DecisionsService
from evermind.signals.models import Signal
from evermind.signals.service import SignalsService
from evermind.tasks.service import TasksService

CONSUMER_NAME = "signals"
logger = logging.getLogger(__name__)


class SignalsConsumer:
    def __init__(self, session: Session):
        self.session = session

    def _offset(self) -> ProjectionOffset:
        row = self.session.get(ProjectionOffset, CONSUMER_NAME)
        if row is None:
            row = ProjectionOffset(consumer=CONSUMER_NAME, last_seq=0)
            self.session.add(row)
            self.session.flush()
        return row

    def poll_and_apply(self) -> int:
        offset = self._offset()
        events = list(
            self.session.scalars(
                select(DomainEvent)
                .where(DomainEvent.seq > offset.last_seq)
                .order_by(DomainEvent.seq)
            )
        )
        for event in events:
            if event.kind == "signal_recorded":
                # A malformed event must not keep this projection pinned on the
                # same paid-extraction window forever.  The savepoint preserves
                # valid prior work and lets the outer transaction advance offset.
                try:
                    with self.session.begin_nested():
                        self._on_signal(event)
                except (KeyError, TypeError, ValueError) as exc:
                    logger.exception("quarantined malformed signal_recorded event %s: %s", event.seq, exc)
            offset.last_seq = event.seq
        return len(events)

    def _on_signal(self, event: DomainEvent) -> None:
        p = event.payload
        # A replay cannot get past its transactionally stored offset; this extra
        # lookup also protects manual event-log repair.
        exists = self.session.scalar(
            select(Signal).where(
                Signal.message_id == p["message_id"],
                Signal.task_id == p.get("task_id"),
                Signal.normalized_topic == p["normalized_topic"],
            )
        )
        if exists is None:
            SignalsService(self.session).emit(
                kind=SignalKind(p["signal_kind"]),
                project_id=p["project_id"],
                task_id=p.get("task_id"),
                party_id=p.get("party_id"),
                normalized_topic=p["normalized_topic"],
                excerpt=p["excerpt"],
                message_id=p["message_id"],
                ts=datetime.fromisoformat(p["ts"]),
                window_id=p.get("window_id") or 0,
                evidence=p.get("evidence") or None,
                waiting_on_text=p.get("waiting_on_text"),
            )
        self.promote_eligible(
            now=event.ts,
            task_id=p.get("task_id"),
            topic=p["normalized_topic"],
            project_id=p["project_id"],
            party_id=p.get("party_id"),
            reporter=p.get("reported_by_user_id"),
        )

    def promote_eligible(
        self,
        *,
        now: datetime | None = None,
        task_id: int | None = None,
        topic: str | None = None,
        project_id: int | None = None,
        party_id: int | None = None,
        reporter: int | None = None,
    ) -> int:
        now = now or datetime.now(timezone.utc)
        service = SignalsService(self.session)
        stmt = select(Signal).where(Signal.status == SignalStatus.OPEN)
        if project_id is not None:
            stmt = stmt.where(
                Signal.project_id == project_id,
                Signal.task_id == task_id,
                Signal.party_id == party_id,
                Signal.normalized_topic == topic,
            )
        rows = list(self.session.scalars(stmt))
        identities = {(s.project_id, s.task_id, s.party_id, s.normalized_topic) for s in rows}
        count = 0
        for pid, tid, party, name in identities:
            promotion = service.try_promote(
                project_id=pid, task_id=tid, party_id=party, normalized_topic=name, now=now
            )
            if promotion is None or tid is None or promotion.kind != SignalKind.BLOCKER:
                continue
            signals = service.open_signals_for_identity(
                project_id=pid, task_id=tid, party_id=party, normalized_topic=name
            )
            task = TasksService(self.session).get_task(tid)
            if task is None:
                continue
            pics = TasksService(self.session).pics_of(tid)
            actor = reporter or (pics[0] if pics else None)
            if actor is None:
                continue
            receipts = {
                (x["message_id"], x.get("rev_at_capture", 1)) for s in signals for x in s.evidence
            }
            waiting_text = next(
                (signal.waiting_on_text for signal in signals if signal.waiting_on_text), None
            )
            waiting = (
                {"party_id": party}
                if party is not None
                else service.resolve_waiting_on(waiting_text or name)
            )
            outcome = DecisionsService(self.session, task_port=TasksService(self.session)).handle(
                ProposeDecision(
                    client_command_id=uuid.uuid5(
                        uuid.NAMESPACE_URL, f"signal-promotion:{pid}:{tid}:{party}:{name}"
                    ),
                    persona=str(actor),
                    created_from=CreatedFrom.LLM,
                    confidence=1.0,
                    ts=promotion.since,
                    source_message_id=signals[0].message_id,
                    decided_by_user_id=actor,
                    reported_by_user_id=actor,
                    force_proposed=True,
                    review_reason="signal_promotion",
                    scope=DecisionScope.TASK,
                    scope_target=f"task:{tid}",
                    description=f"Blocker: {name}",
                    ops=[
                        OpSpec(target=f"task:{tid}", facet="status", op="set", value="blocked"),
                        OpSpec(
                            target=f"task:{tid}",
                            facet="blocked_waiting_on",
                            op="set",
                            value=waiting,
                        ),
                    ],
                    citations=[
                        CitationSpec(message_id=mid, kind=CitationKind.EVIDENCE, rev_at_capture=rev)
                        for mid, rev in sorted(receipts)
                    ],
                ),
                commit=False,
            )
            if outcome.get("status") in {"proposed", "merged_into_pending", "corroborated"}:
                decision_id = (
                    outcome.get("decision_id") or (outcome.get("decision_ids") or [None])[0]
                )
                for signal in signals:
                    signal.status, signal.promoted_decision_id = SignalStatus.PROMOTED, decision_id
                count += 1
        return count

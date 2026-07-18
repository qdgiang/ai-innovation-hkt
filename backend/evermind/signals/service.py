"""Owner: B. Ledger, promotion, radar lamps, overload, escalation
(SIG-1..5, plan.md P2/P3/P4).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import SignalKind, SignalStatus
from evermind.org.service import OrgService
from evermind.signals import promotion, radar
from evermind.signals.models import Signal
from evermind.tasks.service import TasksService


class SignalsService:
    def __init__(self, session: Session):
        self.session = session

    def emit(self, *, kind: SignalKind, project_id: int, normalized_topic: str, excerpt: str,
              message_id: int, ts: datetime, window_id: int, task_id: int | None = None,
              party_id: int | None = None) -> int:
        """SIG-1 — append-only ledger row keyed on the [EVM-013] identity
        (project, task?, party?, normalized_topic). Does NOT auto-promote —
        "one mention never promotes" (design-v2.md §Signals). Returns the new
        signal's id.
        """
        signal = Signal(
            kind=kind, project_id=project_id, task_id=task_id, party_id=party_id,
            normalized_topic=normalized_topic, excerpt=excerpt, message_id=message_id,
            ts=ts, window_id=window_id, status=SignalStatus.OPEN,
        )
        self.session.add(signal)
        self.session.flush()
        return signal.id

    def open_signals_for_identity(self, *, project_id: int, normalized_topic: str,
                                    task_id: int | None = None,
                                    party_id: int | None = None) -> list[Signal]:
        """All accumulated open mentions for one [EVM-013] identity — the input
        to P3's promotion rule (>=2 corroborating, or 1 + staleness).
        """
        stmt = (
            select(Signal)
            .where(Signal.project_id == project_id)
            .where(Signal.normalized_topic == normalized_topic)
            .where(Signal.task_id == task_id)
            .where(Signal.party_id == party_id)
            .where(Signal.status == SignalStatus.OPEN)
            .order_by(Signal.ts)
        )
        return list(self.session.scalars(stmt))

    def try_promote(self, *, project_id: int, normalized_topic: str,
                     task_id: int | None = None, party_id: int | None = None,
                     now: datetime | None = None) -> promotion.PromotionDecision | None:
        """SIG-1 promotion. Evaluates the pure rule (`signals.promotion.evaluate`
        — >=2 corroborating, or 1 + staleness) against every open signal for
        this identity; returns the `PromotionDecision` that WOULD be submitted,
        or None if not (yet) eligible.

        Actually submitting it — a `RecordSignal` command through
        `decisions.service.handle` (never a direct write to `tasks.blocked_*`,
        architecture.md: signals "must NOT ... mutate tasks; it proposes via
        commands") — is blocked on DEC-1..9 existing (Lane A, still
        NotImplementedError); wire that call here once it does.
        """
        open_signals = self.open_signals_for_identity(
            project_id=project_id, normalized_topic=normalized_topic,
            task_id=task_id, party_id=party_id,
        )
        return promotion.evaluate(open_signals, now=now or datetime.now(timezone.utc))

    def resolve_waiting_on(self, text: str) -> dict:
        """SIG-2 — `waiting_on` resolution: fuzzy-match `text` against known
        `parties` via `org.service` (signals IS on org's read-port allowlist,
        architecture.md), else keep the free text (G22). `org.service.
        match_party_alias` doesn't exist yet (Lane A) — this call will raise
        NotImplementedError until it does; the fallback-to-text branch below
        is what SIG-2 actually promises when no match is found.
        """
        party = OrgService(self.session).match_party_alias(text)
        if party is not None:
            return {"party_id": party.id}
        return {"waiting_on_text": text}

    def radar_sweep(self, *, project_id: int | None = None,
                     now: datetime | None = None) -> list[dict]:
        """SIG-3 — daily job: sweep every non-terminal task for lamps (blocked/
        overdue/stale/idle/late-start/contested — `at_risk` is a documented gap,
        see radar.py). Cadence/dedup (PIC day1 -> LCA day3 -> every 3 days, max
        one entry/task/day) is a `surfacing` feed concern (SRF-1), not this
        method's — this returns every currently-triggered lamp, unfiltered.
        """
        now = now or datetime.now(timezone.utc)
        tasks_service = TasksService(self.session)
        entries: list[dict] = []
        for task in tasks_service.list_tasks(project_id=project_id):
            if task.status in ("done", "canceled", "merged"):
                continue
            snapshot = radar.TaskSnapshot(
                task_id=task.id, status=task.status, start_date=task.start_date,
                end_date=task.end_date, last_event_at=tasks_service.last_event_at(task.id),
            )
            flips = tasks_service.status_flip_actors(
                task.id, since=now - timedelta(days=radar.CONTESTED_WINDOW_DAYS),
            )
            lamps = radar.sweep_task(snapshot, now=now, status_flip_actors=flips)
            for lamp in lamps:
                entries.append({"task_id": task.id, "lamp": lamp})
        return entries

    def escalation_for_dependency_edge(self, predecessor_task_id: int,
                                         successor_task_id: int) -> list[dict]:
        """SIG-5 — cross-boundary (campaign<->program) escalation: one card per
        endpoint side, each carrying its own task plus only a carve-out
        projection (id + status) of the other side (G63). Same-project LCA
        routing needs `org.service.manager_chain` (Lane A, not built) — that
        path isn't wired here yet.
        """
        tasks_service = TasksService(self.session)
        predecessor = tasks_service.get_task(predecessor_task_id)
        successor = tasks_service.get_task(successor_task_id)
        if predecessor is None or successor is None:
            raise LookupError("both tasks must exist")
        if predecessor.project_id == successor.project_id:
            return []  # same-project: not a cross-boundary escalation

        return [
            {
                "own_task_id": predecessor.id,
                "carve_out": {"task_id": successor.id, "status": successor.status},
            },
            {
                "own_task_id": successor.id,
                "carve_out": {"task_id": predecessor.id, "status": predecessor.status},
            },
        ]

    def overload_for(self, user_id: int, *, now: datetime | None = None) -> dict:
        """SIG-4 — per-day concurrent load, next 14 days, across ALL the
        person's teams (already implicit: `list_tasks(pic_user_id=...)` isn't
        project-scoped). Weight: urgent x2, due-<=7d extra. Warn-don't-block —
        this only reports; EVM-017 bounds it (no history mining, no rankings,
        no cross-person comparison — by construction, since it only takes a
        single user_id).
        """
        now = now or datetime.now(timezone.utc)
        my_tasks = TasksService(self.session).list_tasks(
            pic_user_id=user_id, statuses=("todo", "doing"),
        )
        load_by_day: dict[str, float] = {}
        for day_offset in range(14):
            day = (now + timedelta(days=day_offset)).date()
            load = 0.0
            for task in my_tasks:
                start = task.start_date.date() if task.start_date else None
                end = task.end_date.date() if task.end_date else None
                if start is not None and day < start:
                    continue
                if end is not None and day > end:
                    continue
                weight = 2.0 if task.type == "urgent" else 1.0
                if end is not None and (end - now.date()).days <= 7:
                    weight += 1.0
                load += weight
            load_by_day[day.isoformat()] = load
        return {"user_id": user_id, "load_by_day": load_by_day}

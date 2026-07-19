"""Owner: B. Job DEFINITIONS only — job logic lives in the owning module's
service (architecture.md: scheduler "must NOT contain job logic (calls module
ports)"). APScheduler in-process (OPS-4, plan.md P4).
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from evermind.config import settings


def build_scheduler(session_factory) -> BackgroundScheduler:
    """Wires jobs against ORG_TIMEZONE (G54); each job opens its own session
    via `session_factory` and calls the owning module's service — never
    inlines business logic here. Each job commits its own transaction (the
    job boundary is the natural top-level write boundary here).
    """
    # misfire_grace_time: the default (1s) skips runs entirely when the tick
    # lands late (seen live: ~3s drift under Docker/Windows -> every 30s
    # extraction beat logged "missed" and never ran). coalesce folds a backlog
    # of missed runs into one; max_instances stops overlap when a beat
    # (an LLM call) outlives the interval.
    scheduler = BackgroundScheduler(
        timezone=settings.org_timezone,
        job_defaults={"misfire_grace_time": 30, "coalesce": True, "max_instances": 1},
    )

    def radar_job() -> None:
        """SIG-3 sweep -> SRF-1 feed entries, per PIC (design-v2.md: "sweep
        lamps -> dashboard feed entries")."""
        from evermind.surfacing.service import SurfacingService
        with session_factory() as session:
            SurfacingService(session).raise_radar_lamps_to_feed()
            session.commit()

    def nudge_job() -> None:
        """TODO(B, blocked on Lane A): DEC-7 anti-rot visibility — 48h approver
        nudge (settled #18: this only touches visibility, never a decision's
        status). Needs `decisions`' proposed-and-aging data, which doesn't
        exist yet."""
        raise NotImplementedError

    def capture_self_check_job() -> None:
        from evermind.connectors.health import CaptureHealthService
        with session_factory() as session:
            CaptureHealthService(session).check_all_groups()
            session.commit()

    def extraction_job() -> None:
        """ING-2..5 — the periodic LLM extraction beat: window + extract every
        chat group's pending messages (EXTRACTION_INTERVAL_SEC; the same call
        `POST /ingestion/extract` triggers manually)."""
        from evermind.ingestion.service import IngestionService
        with session_factory() as session:
            IngestionService(session).run_pending_windows()
            session.commit()

    def promotion_job() -> None:
        """SIG-1 promotion beat: evaluate every open ledger identity
        (≥2 corroborating mentions, or 1 + staleness) — promoted blockers
        surface on the board, task-linked ones become a PROPOSED blocked-state
        decision through the gateway (a human still confirms; settled #18's
        clocks-only-create-visibility stays true for decisions)."""
        from evermind.decisions.service import DecisionsService
        from evermind.signals.service import SignalsService
        from evermind.tasks.service import TasksService
        with session_factory() as session:
            gateway = DecisionsService(session, task_port=TasksService(session))
            SignalsService(session).promotion_sweep(decisions_service=gateway)
            session.commit()

    scheduler.add_job(radar_job, CronTrigger(hour=6))
    scheduler.add_job(capture_self_check_job, CronTrigger(hour="*"))
    if settings.extraction_interval_sec > 0:
        scheduler.add_job(extraction_job,
                          IntervalTrigger(seconds=settings.extraction_interval_sec))
    if settings.promotion_sweep_sec > 0:
        scheduler.add_job(promotion_job,
                          IntervalTrigger(seconds=settings.promotion_sweep_sec))
    return scheduler

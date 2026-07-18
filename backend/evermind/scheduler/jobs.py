"""Owner: B. Job DEFINITIONS only — job logic lives in the owning module's
service (architecture.md: scheduler "must NOT contain job logic (calls module
ports)"). APScheduler in-process (OPS-4, plan.md P4).
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from evermind.config import settings


def build_scheduler(session_factory) -> BackgroundScheduler:
    """Wires jobs against ORG_TIMEZONE (G54); each job opens its own session
    via `session_factory` and calls the owning module's service — never
    inlines business logic here. Each job commits its own transaction (the
    job boundary is the natural top-level write boundary here).
    """
    scheduler = BackgroundScheduler(timezone=settings.org_timezone)

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

    scheduler.add_job(radar_job, CronTrigger(hour=6))
    scheduler.add_job(capture_self_check_job, CronTrigger(hour="*"))
    return scheduler

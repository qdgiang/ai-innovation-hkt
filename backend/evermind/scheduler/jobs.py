"""Owner: B. Job DEFINITIONS only — job logic lives in the owning module's
service (architecture.md: scheduler "must NOT contain job logic (calls module
ports)"). APScheduler in-process (OPS-4, plan.md P4).
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from evermind.config import settings


def build_scheduler(session_factory) -> BackgroundScheduler:
    """TODO(B): wire jobs against ORG_TIMEZONE (G54); each job opens its own
    session via `session_factory` and calls the owning module's service —
    never inlines business logic here.
    """
    scheduler = BackgroundScheduler(timezone=settings.org_timezone)

    def radar_job() -> None:
        from evermind.signals.service import SignalsService
        with session_factory() as session:
            SignalsService(session).radar_sweep()

    def nudge_job() -> None:
        """TODO(B): DEC-7 anti-rot visibility — 48h approver nudge (settled #18:
        this only touches visibility, never a decision's status)."""
        raise NotImplementedError

    def capture_self_check_job() -> None:
        from evermind.connectors.health import CaptureHealthService
        with session_factory() as session:
            CaptureHealthService(session).check_all_groups()

    scheduler.add_job(radar_job, CronTrigger(hour=6))
    scheduler.add_job(capture_self_check_job, CronTrigger(hour="*"))
    return scheduler

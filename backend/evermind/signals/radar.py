"""Owner: B. SIG-3 radar lamps — pure logic (mirrors `signals/promotion.py` and
`tasks/fold.py`'s separation of rule-from-wiring). One task's current state +
a little history in, a set of triggered lamp names out.

`at_risk` (design-v2.md: "slack below threshold") is deliberately NOT
implemented here — the schema has no effort/estimate field to compute slack
from (data-model.md's `tasks` table has only start/end dates), and no other
doc pins a concrete formula. Flagged as a gap rather than guessed at.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_STALE_DAYS = 5  # not pinned by design-v2.md/data-model.md; a placeholder default
IDLE_DAYS = 14  # G56, explicit
CONTESTED_MIN_FLIPS = 3  # G55, explicit (K)
CONTESTED_WINDOW_DAYS = 7  # G55, explicit (T)
CONTESTED_MIN_ACTORS = 2  # G55, explicit


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive timestamps while Postgres returns aware ones."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass
class TaskSnapshot:
    task_id: int
    status: str
    start_date: datetime | None
    end_date: datetime | None
    last_event_at: datetime | None


def sweep_task(snapshot: TaskSnapshot, *, now: datetime,
               status_flip_actors: list[tuple[datetime, int]],
               stale_days: int = DEFAULT_STALE_DAYS) -> set[str]:
    """Lamps for one task. `status_flip_actors` = every (ts, actor_user_id) of
    a status-kind task_update, any age (the contested window is applied here).
    """
    now = _as_utc(now)
    start_date = _as_utc(snapshot.start_date) if snapshot.start_date else None
    end_date = _as_utc(snapshot.end_date) if snapshot.end_date else None
    last_event_at = _as_utc(snapshot.last_event_at) if snapshot.last_event_at else None
    lamps: set[str] = set()
    terminal = snapshot.status in ("done", "canceled", "merged")

    if snapshot.status == "blocked":
        lamps.add("blocked")

    if not terminal and end_date is not None and end_date < now:
        lamps.add("overdue")

    if snapshot.status == "todo" and start_date is not None and start_date < now:
        lamps.add("late-start")

    if snapshot.status == "doing":
        quiet_since = now - last_event_at if last_event_at else None
        if quiet_since is None or quiet_since >= timedelta(days=stale_days):
            lamps.add("stale")

    if snapshot.status == "todo":
        quiet_since = now - last_event_at if last_event_at else None
        if quiet_since is None or quiet_since >= timedelta(days=IDLE_DAYS):
            lamps.add("idle")  # G56 — catches dateless/unowned work no other lamp sees

    window_start = now - timedelta(days=CONTESTED_WINDOW_DAYS)
    recent_flips = [(_as_utc(ts), actor) for ts, actor in status_flip_actors if _as_utc(ts) >= window_start]
    distinct_actors = {actor for _, actor in recent_flips}
    if len(recent_flips) >= CONTESTED_MIN_FLIPS and len(distinct_actors) >= CONTESTED_MIN_ACTORS:
        lamps.add("contested")  # G55 — suggest compose-split

    return lamps

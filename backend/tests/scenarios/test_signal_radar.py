"""L1 — SIG-3 radar lamps + SIG-5 escalation (plan.md P4 Lane B)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from evermind.contracts.enums import ProjectKind
from evermind.signals.radar import TaskSnapshot, sweep_task
from evermind.signals.service import SignalsService
from evermind.tasks.models import Task

T0 = datetime(2026, 9, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The pure rule (sweep_task)
# ---------------------------------------------------------------------------


def test_blocked_status_lamps_blocked():
    snap = TaskSnapshot(task_id=1, status="blocked", start_date=None, end_date=None,
                         last_event_at=None)
    assert "blocked" in sweep_task(snap, now=T0, status_flip_actors=[])


def test_overdue_when_end_date_passed_and_not_terminal():
    snap = TaskSnapshot(task_id=1, status="doing", start_date=None,
                         end_date=T0 - timedelta(days=1), last_event_at=T0)
    assert "overdue" in sweep_task(snap, now=T0, status_flip_actors=[])


def test_not_overdue_when_done():
    snap = TaskSnapshot(task_id=1, status="done", start_date=None,
                         end_date=T0 - timedelta(days=1), last_event_at=T0)
    assert "overdue" not in sweep_task(snap, now=T0, status_flip_actors=[])


def test_late_start_when_todo_past_start_date():
    snap = TaskSnapshot(task_id=1, status="todo", start_date=T0 - timedelta(days=1),
                         end_date=None, last_event_at=None)
    assert "late-start" in sweep_task(snap, now=T0, status_flip_actors=[])


def test_stale_when_doing_with_no_recent_event():
    fresh = TaskSnapshot(task_id=1, status="doing", start_date=None, end_date=None,
                         last_event_at=T0 - timedelta(days=1))
    stale = TaskSnapshot(task_id=1, status="doing", start_date=None, end_date=None,
                         last_event_at=T0 - timedelta(days=10))
    assert "stale" not in sweep_task(fresh, now=T0, status_flip_actors=[])
    assert "stale" in sweep_task(stale, now=T0, status_flip_actors=[])


def test_idle_when_todo_and_no_event_for_14_days_g56():
    """G56 — catches dateless/unowned program work no other lamp can see."""
    fresh = TaskSnapshot(task_id=1, status="todo", start_date=None, end_date=None,
                         last_event_at=T0 - timedelta(days=5))
    idle = TaskSnapshot(task_id=1, status="todo", start_date=None, end_date=None,
                        last_event_at=T0 - timedelta(days=15))
    never_touched = TaskSnapshot(task_id=1, status="todo", start_date=None, end_date=None,
                                 last_event_at=None)
    assert "idle" not in sweep_task(fresh, now=T0, status_flip_actors=[])
    assert "idle" in sweep_task(idle, now=T0, status_flip_actors=[])
    assert "idle" in sweep_task(never_touched, now=T0, status_flip_actors=[])


def test_contested_needs_3_flips_by_2_distinct_actors_within_7_days_g55():
    snap = TaskSnapshot(task_id=1, status="doing", start_date=None, end_date=None,
                        last_event_at=T0)
    two_actors_three_flips = [
        (T0 - timedelta(days=1), 101), (T0 - timedelta(days=2), 102),
        (T0 - timedelta(days=3), 101),
    ]
    one_actor_only = [
        (T0 - timedelta(days=1), 101), (T0 - timedelta(days=2), 101),
        (T0 - timedelta(days=3), 101),
    ]
    outside_window = [
        (T0 - timedelta(days=10), 101), (T0 - timedelta(days=11), 102),
        (T0 - timedelta(days=12), 101),
    ]
    assert "contested" in sweep_task(snap, now=T0, status_flip_actors=two_actors_three_flips)
    assert "contested" not in sweep_task(snap, now=T0, status_flip_actors=one_actor_only)
    assert "contested" not in sweep_task(snap, now=T0, status_flip_actors=outside_window)


# ---------------------------------------------------------------------------
# radar_sweep — wired against real tasks
# ---------------------------------------------------------------------------


def test_radar_sweep_skips_terminal_tasks(db_session: Session):
    db_session.add(Task(id=1, project_id=10, kind="project", description="x", status="done"))
    db_session.add(Task(id=2, project_id=10, kind="project", description="y", status="blocked"))
    db_session.flush()

    entries = SignalsService(db_session).radar_sweep(project_id=10, now=T0)
    task_ids_flagged = {e["task_id"] for e in entries}
    assert 1 not in task_ids_flagged
    assert 2 in task_ids_flagged


# ---------------------------------------------------------------------------
# escalation_for_dependency_edge
# ---------------------------------------------------------------------------


def test_escalation_raises_one_card_per_side_across_projects(db_session: Session):
    db_session.add(Task(id=1, project_id=10, project_kind=ProjectKind.CAMPAIGN,
                         kind="project", description="campaign task", status="doing"))
    db_session.add(Task(id=2, project_id=20, project_kind=ProjectKind.PROGRAM,
                         kind="ongoing", description="program task", status="todo"))
    db_session.flush()

    cards = SignalsService(db_session).escalation_for_dependency_edge(1, 2)
    assert len(cards) == 2
    own_ids = {c["own_task_id"] for c in cards}
    assert own_ids == {1, 2}
    card_for_1 = next(c for c in cards if c["own_task_id"] == 1)
    assert card_for_1["carve_out"] == {"task_id": 2, "status": "todo"}


def test_no_escalation_within_the_same_project(db_session: Session):
    db_session.add(Task(id=1, project_id=10, kind="project", description="a", status="doing"))
    db_session.add(Task(id=2, project_id=10, kind="project", description="b", status="todo"))
    db_session.flush()

    cards = SignalsService(db_session).escalation_for_dependency_edge(1, 2)
    assert cards == []

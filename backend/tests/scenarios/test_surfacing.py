"""L1 — SRF-1/2/3 (plan.md P4 Lane B)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from evermind.surfacing.service import SurfacingService
from evermind.tasks.models import Task, TaskAssignment, TaskTeam, TaskUpdate

T0 = datetime(2026, 9, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# SRF-1 — feed
# ---------------------------------------------------------------------------


def test_feed_entry_dedups_within_batch_window(db_session: Session):
    service = SurfacingService(db_session)
    first = service.add_feed_entry(
        persona_user_id=1, kind="lamp:stale", payload={"a": 1}, batch_key="k1", ts=T0,
    )
    second = service.add_feed_entry(
        persona_user_id=1, kind="lamp:stale", payload={"a": 2},
        batch_key="k1", ts=T0 + timedelta(minutes=10),
    )
    assert first == second  # same batch window -> no duplicate

    entries = service.feed_for(1)
    assert len(entries) == 1


def test_feed_entry_does_not_dedup_after_batch_window(db_session: Session):
    service = SurfacingService(db_session)
    first = service.add_feed_entry(
        persona_user_id=1, kind="lamp:stale", payload={}, batch_key="k1", ts=T0,
    )
    second = service.add_feed_entry(
        persona_user_id=1, kind="lamp:stale", payload={},
        batch_key="k1", ts=T0 + timedelta(minutes=45),
    )
    assert first != second
    assert len(service.feed_for(1)) == 2


def test_retraction_appends_and_links_back(db_session: Session):
    service = SurfacingService(db_session)
    original = service.add_feed_entry(
        persona_user_id=1, kind="decision", payload={"d": 1}, batch_key="k2", ts=T0,
    )
    retraction_id = service.record_retraction(original, payload={"reason": "overruled"})

    entries = {e.id: e for e in service.feed_for(1)}
    assert entries[original].superseded_by_entry == retraction_id
    assert entries[retraction_id].kind == "retraction"


def test_raise_radar_lamps_to_feed_notifies_every_pic(db_session: Session):
    db_session.add(Task(id=1, project_id=10, kind="project", description="x", status="blocked"))
    db_session.add(TaskAssignment(task_id=1, user_id=101))
    db_session.add(TaskAssignment(task_id=1, user_id=102))
    db_session.flush()

    count = SurfacingService(db_session).raise_radar_lamps_to_feed(project_id=10, now=T0)
    assert count == 2  # one lamp (blocked) x 2 PICs

    feed_101 = SurfacingService(db_session).feed_for(101)
    feed_102 = SurfacingService(db_session).feed_for(102)
    assert len(feed_101) == 1
    assert len(feed_102) == 1
    assert feed_101[0].payload["lamp"] == "blocked"


# ---------------------------------------------------------------------------
# SRF-2 — inbox
# ---------------------------------------------------------------------------


def test_inbox_add_and_resolve(db_session: Session):
    service = SurfacingService(db_session)
    item_id = service.add_inbox_item(persona_user_id=1, kind="proposal", ref_id=99, created_at=T0)

    open_items = service.inbox_for(1)
    assert len(open_items) == 1
    assert open_items[0].kind == "proposal"

    service.resolve_inbox_item(item_id, resolution="approved", resolved_at=T0 + timedelta(hours=1))
    assert service.inbox_for(1) == []  # resolved -> no longer "open"
    assert len(service.inbox_for(1, include_resolved=True)) == 1


# ---------------------------------------------------------------------------
# SRF-3 — digest
# ---------------------------------------------------------------------------


def test_digest_for_team_aggregates_tasks_blockers_and_wrap_note(db_session: Session):
    db_session.add(Task(id=1, project_id=10, kind="project", description="a", status="doing"))
    db_session.add(Task(id=2, project_id=10, kind="project", description="b", status="blocked",
                         blocked_waiting_on_text="vendor", blocked_since=T0))
    db_session.add(TaskTeam(task_id=1, team_id=5))
    db_session.add(TaskTeam(task_id=2, team_id=5))
    db_session.flush()
    db_session.add(TaskUpdate(
        ts=T0, recorded_at=T0, task_id=1, actor_user_id=42, kind="note",
        payload={"text": "tuần này ổn, còn 2 việc"}, created_from="marker",
    ))
    db_session.flush()

    digest = SurfacingService(db_session).digest_for(5, now=T0 + timedelta(hours=1))
    assert digest["tasks_by_status"] == {"doing": 1, "blocked": 1}
    assert len(digest["blockers"]) == 1
    assert digest["blockers"][0]["task_id"] == 2
    assert digest["wrap_note"] == "tuần này ổn, còn 2 việc"
    assert digest["wrap_note_by"] == 42

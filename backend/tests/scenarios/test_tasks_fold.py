"""L1 — `tasks` module (TSK-1/2/3/6/8), plan.md P1 Lane B.

Exercised against a SYNTHETIC `domain_events` stream (constructed directly in
these tests) rather than through `POST /commands`, per plan.md's P1 note:
"fold tested against synthetic domain_events until A's gateway lands." Once
`decisions.service` (DEC-1..9) exists, an additional command-driven L1 suite
should reproduce the same assertions end-to-end (plan.md P1 exit criterion).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from evermind.contracts.enums import ProjectKind
from evermind.db.eventlog import DomainEvent
from evermind.tasks.consumer import TasksConsumer
from evermind.tasks.dependencies import DependencyCycleError, DependencyNotAdmittedError
from evermind.tasks.models import Task, TaskAssignment, TaskDependency
from evermind.tasks.service import TasksService

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _emit(session: Session, *, ts: datetime, kind: str, aggregate: str,
          aggregate_id: int, payload: dict) -> DomainEvent:
    event = DomainEvent(
        ts=ts, kind=kind, aggregate=aggregate, aggregate_id=aggregate_id, payload=payload,
    )
    session.add(event)
    session.flush()
    return event


def _decision_effective(session: Session, *, ts: datetime, decision_id: int, ops: list[dict]):
    return _emit(
        session, ts=ts, kind="decision_effective", aggregate="decision",
        aggregate_id=decision_id, payload={"decision_id": decision_id, "ops": ops},
    )


# ---------------------------------------------------------------------------
# TSK-1 — the fold
# ---------------------------------------------------------------------------


def test_decision_effective_creates_and_sets_task_fields(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "Book the venue"},
        {"target": "task:1", "facet": "status", "op": "set", "value": "doing"},
        {"target": "task:1", "facet": "kind", "op": "set", "value": "project"},
    ])
    applied = TasksConsumer(db_session).poll_and_apply()
    assert applied == 1

    task = db_session.get(Task, 1)
    assert task is not None
    assert task.description == "Book the venue"
    assert task.status == "doing"


def test_assignment_add_remove_set(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "x"},
        {"target": "task:1", "facet": "assignment", "op": "add", "value": 101},
        {"target": "task:1", "facet": "assignment", "op": "add", "value": 102},
    ])
    TasksConsumer(db_session).poll_and_apply()
    assignees = {a.user_id for a in db_session.query(TaskAssignment).filter_by(task_id=1)}
    assert assignees == {101, 102}

    _decision_effective(db_session, ts=T0 + timedelta(minutes=1), decision_id=2, ops=[
        {"target": "task:1", "facet": "assignment", "op": "remove", "value": 101},
    ])
    TasksConsumer(db_session).poll_and_apply()
    assignees = {a.user_id for a in db_session.query(TaskAssignment).filter_by(task_id=1)}
    assert assignees == {102}

    _decision_effective(db_session, ts=T0 + timedelta(minutes=2), decision_id=3, ops=[
        {"target": "task:1", "facet": "assignment", "op": "set", "value": [201, 202]},
    ])
    TasksConsumer(db_session).poll_and_apply()
    assignees = {a.user_id for a in db_session.query(TaskAssignment).filter_by(task_id=1)}
    assert assignees == {201, 202}  # G1: multi-PIC via per-slot ops


def test_note_append_never_overwrites(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "x"},
        {"target": "task:1", "facet": "note", "op": "append", "value": "first note"},
    ])
    _decision_effective(db_session, ts=T0 + timedelta(minutes=1), decision_id=2, ops=[
        {"target": "task:1", "facet": "note", "op": "append", "value": "second note"},
    ])
    TasksConsumer(db_session).poll_and_apply()
    task = db_session.get(Task, 1)
    assert "first note" in task.note
    assert "second note" in task.note


def test_multiop_decision_only_touches_its_own_targets(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "task one"},
        {"target": "task:2", "facet": "description", "op": "set", "value": "task two"},
    ])
    TasksConsumer(db_session).poll_and_apply()
    assert db_session.get(Task, 1).description == "task one"
    assert db_session.get(Task, 2).description == "task two"


def test_end_date_defaulting_flag_and_human_confirm_clears_it(db_session: Session):
    """TSK-7: `decisions` computes the campaign default upstream (tasks can't
    read `org`); the fold just records the value + the flag it's handed, and
    clears the flag when a later op supplies a plain (human-confirmed) value.
    """
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "x"},
        {"target": "task:1", "facet": "end_date", "op": "set",
         "value": {"value": "2026-09-25", "end_date_defaulted": True}},
    ])
    TasksConsumer(db_session).poll_and_apply()
    task = db_session.get(Task, 1)
    assert str(task.end_date) == "2026-09-25"
    assert task.end_date_defaulted is True

    _decision_effective(db_session, ts=T0 + timedelta(minutes=1), decision_id=2, ops=[
        {"target": "task:1", "facet": "end_date", "op": "set", "value": "2026-09-20"},
    ])
    TasksConsumer(db_session).poll_and_apply()
    task = db_session.get(Task, 1)
    assert str(task.end_date) == "2026-09-20"
    assert task.end_date_defaulted is False


# ---------------------------------------------------------------------------
# TSK-2 — update lanes (G7 PIC auto-apply) + TSK-6 terminal locks
# ---------------------------------------------------------------------------


def test_task_update_recorded_applies_pic_status_and_is_pic_reads_back(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "x"},
        {"target": "task:1", "facet": "assignment", "op": "add", "value": 101},
    ])
    _emit(db_session, ts=T0 + timedelta(hours=1), kind="task_update_recorded",
          aggregate="task_update", aggregate_id=1, payload={
              "task_id": 1, "actor_user_id": 101, "kind": "status",
              "payload": {"status": "done"}, "created_from": "marker",
              "confidence": None, "source_message_id": 42,
          })
    TasksConsumer(db_session).poll_and_apply()

    task = db_session.get(Task, 1)
    assert task.status == "done"
    service = TasksService(db_session)
    assert service.is_pic(1, 101) is True
    assert service.is_pic(1, 999) is False


def test_terminal_lock_after_cancel(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "x"},
        {"target": "task:1", "facet": "status", "op": "set", "value": "canceled"},
    ])
    TasksConsumer(db_session).poll_and_apply()
    assert TasksService(db_session).is_terminal(1) is True


# ---------------------------------------------------------------------------
# TSK-3 — dependencies: DAG cycle check + G51 admission matrix + EVM-006
# ---------------------------------------------------------------------------


def _make_task(session: Session, task_id: int, project_id: int,
                project_kind: ProjectKind = ProjectKind.PROGRAM) -> Task:
    task = Task(id=task_id, project_id=project_id, project_kind=project_kind,
                kind="project", description=f"task {task_id}")
    session.add(task)
    session.flush()
    return task


def test_dependency_same_project_allowed(db_session: Session):
    _make_task(db_session, 1, project_id=10)
    _make_task(db_session, 2, project_id=10)
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "dependency", "op": "add",
         "value": {"successor_task_id": 2}},
    ])
    TasksConsumer(db_session).poll_and_apply()
    edge = db_session.get(TaskDependency, {"predecessor_task_id": 1, "successor_task_id": 2})
    assert edge is not None
    assert edge.status == "requested"


def test_dependency_campaign_to_different_campaign_denied(db_session: Session):
    _make_task(db_session, 1, project_id=10, project_kind=ProjectKind.CAMPAIGN)
    _make_task(db_session, 2, project_id=20, project_kind=ProjectKind.CAMPAIGN)
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "dependency", "op": "add",
         "value": {"successor_task_id": 2}},
    ])
    with pytest.raises(DependencyNotAdmittedError):
        TasksConsumer(db_session).poll_and_apply()


def test_dependency_campaign_to_program_allowed_g51(db_session: Session):
    _make_task(db_session, 1, project_id=10, project_kind=ProjectKind.CAMPAIGN)
    _make_task(db_session, 2, project_id=20, project_kind=ProjectKind.PROGRAM)
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "dependency", "op": "add",
         "value": {"successor_task_id": 2}},
    ])
    TasksConsumer(db_session).poll_and_apply()
    edge = db_session.get(TaskDependency, {"predecessor_task_id": 1, "successor_task_id": 2})
    assert edge is not None


def test_dependency_cycle_rejected(db_session: Session):
    _make_task(db_session, 1, project_id=10)
    _make_task(db_session, 2, project_id=10)
    _make_task(db_session, 3, project_id=10)
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "dependency", "op": "add",
         "value": {"successor_task_id": 2}},
    ])
    _decision_effective(db_session, ts=T0 + timedelta(minutes=1), decision_id=2, ops=[
        {"target": "task:2", "facet": "dependency", "op": "add",
         "value": {"successor_task_id": 3}},
    ])
    TasksConsumer(db_session).poll_and_apply()

    _decision_effective(db_session, ts=T0 + timedelta(minutes=2), decision_id=3, ops=[
        {"target": "task:3", "facet": "dependency", "op": "add",
         "value": {"successor_task_id": 1}},  # 1 -> 2 -> 3 -> 1
    ])
    with pytest.raises(DependencyCycleError):
        TasksConsumer(db_session).poll_and_apply()


def test_canceled_predecessor_flips_dependents_to_needs_rewire(db_session: Session):
    """[EVM-006]: only `done` satisfies; canceled -> needs_rewire, never silently
    unblocked."""
    _make_task(db_session, 1, project_id=10)
    _make_task(db_session, 2, project_id=10)
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "dependency", "op": "add",
         "value": {"successor_task_id": 2}},
    ])
    TasksConsumer(db_session).poll_and_apply()

    _decision_effective(db_session, ts=T0 + timedelta(minutes=1), decision_id=2, ops=[
        {"target": "task:1", "facet": "status", "op": "set", "value": "canceled"},
    ])
    TasksConsumer(db_session).poll_and_apply()

    edge = db_session.get(TaskDependency, {"predecessor_task_id": 1, "successor_task_id": 2})
    assert edge.status == "needs_rewire"


# ---------------------------------------------------------------------------
# TSK-8 — time travel
# ---------------------------------------------------------------------------


def test_time_travel_reconstructs_state_before_and_after_supersession(db_session: Session):
    """Mirrors the D1(Phuong Liet)->D2(Nguyen Du) venue-switch shape from data-v2."""
    t_d1 = T0
    t_d2 = T0 + timedelta(days=3)
    _decision_effective(db_session, ts=t_d1, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "book venue"},
        {"target": "task:1", "facet": "attr:venue", "op": "set", "value": "Phuong Liet"},
        {"target": "task:1", "facet": "status", "op": "set", "value": "doing"},
    ])
    _decision_effective(db_session, ts=t_d2, decision_id=2, ops=[
        {"target": "task:1", "facet": "status", "op": "set", "value": "done"},
    ])
    TasksConsumer(db_session).poll_and_apply()

    service = TasksService(db_session)
    before = service.at(1, t_d1 + timedelta(hours=1))
    after = service.at(1, t_d2 + timedelta(hours=1))
    assert before["status"] == "doing"
    assert after["status"] == "done"


def test_time_travel_ignores_ops_for_other_tasks_in_same_decision(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "description", "op": "set", "value": "task one"},
        {"target": "task:2", "facet": "description", "op": "set", "value": "task two"},
    ])
    TasksConsumer(db_session).poll_and_apply()
    state = TasksService(db_session).at(1, T0 + timedelta(hours=1))
    assert state["description"] == "task one"


# ---------------------------------------------------------------------------
# Write plumbing — idempotent consumption via ProjectionOffset
# ---------------------------------------------------------------------------


def test_poll_and_apply_is_idempotent_across_calls(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "assignment", "op": "add", "value": 101},
    ])
    first = TasksConsumer(db_session).poll_and_apply()
    second = TasksConsumer(db_session).poll_and_apply()
    assert first == 1
    assert second == 0  # no new events since the offset advanced
    assignees = {a.user_id for a in db_session.query(TaskAssignment).filter_by(task_id=1)}
    assert assignees == {101}  # not double-applied


# ---------------------------------------------------------------------------
# DEC-6 — rejection of a once-effective decision retracts it from replay
# ---------------------------------------------------------------------------


def test_decision_rejected_excludes_it_from_future_replay(db_session: Session):
    _decision_effective(db_session, ts=T0, decision_id=1, ops=[
        {"target": "task:1", "facet": "status", "op": "set", "value": "doing"},
    ])
    TasksConsumer(db_session).poll_and_apply()
    assert TasksService(db_session).at(1, T0 + timedelta(hours=1))["status"] == "doing"

    _emit(db_session, ts=T0 + timedelta(hours=2), kind="decision_rejected",
          aggregate="decision", aggregate_id=1, payload={"decision_id": 1})
    TasksConsumer(db_session).poll_and_apply()

    assert TasksService(db_session).at(1, T0 + timedelta(hours=3))["status"] == "todo"

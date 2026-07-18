"""L1 — TSK-4 merge & split, TSK-5 cross-project transfer (plan.md P6)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from evermind.contracts.enums import ProjectKind
from evermind.tasks.consumer import TasksConsumer
from evermind.tasks.dependencies import DependencyCycleError
from evermind.tasks.merge import merge_tasks
from evermind.tasks.models import (
    Task, TaskAssignment, TaskDependency, TaskTeam, TaskUpdate,
)
from evermind.db.eventlog import DomainEvent

T0 = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _make_task(session: Session, task_id: int, project_id: int = 10,
                project_kind: ProjectKind = ProjectKind.PROGRAM, status: str = "doing") -> Task:
    task = Task(id=task_id, project_id=project_id, project_kind=project_kind,
                kind="project", description=f"task {task_id}", status=status)
    session.add(task)
    session.flush()
    return task


# ---------------------------------------------------------------------------
# TSK-4 — merge (G43/G60)
# ---------------------------------------------------------------------------


def test_merge_unions_assignments_and_teams(db_session: Session):
    _make_task(db_session, 1)
    _make_task(db_session, 2)
    db_session.add(TaskAssignment(task_id=1, user_id=101))
    db_session.add(TaskAssignment(task_id=2, user_id=101))  # overlap, dedup
    db_session.add(TaskAssignment(task_id=2, user_id=102))
    db_session.add(TaskTeam(task_id=2, team_id=5))
    db_session.flush()

    merge_tasks(db_session, absorbed_id=2, survivor_id=1)

    assignees = {a.user_id for a in db_session.query(TaskAssignment).filter_by(task_id=1)}
    assert assignees == {101, 102}
    teams = {t.team_id for t in db_session.query(TaskTeam).filter_by(task_id=1)}
    assert teams == {5}


def test_merge_marks_absorbed_as_merged_husk(db_session: Session):
    _make_task(db_session, 1)
    _make_task(db_session, 2)
    db_session.flush()

    merge_tasks(db_session, absorbed_id=2, survivor_id=1)

    absorbed = db_session.get(Task, 2)
    assert absorbed.status == "merged"
    assert absorbed.merged_into == 1


def test_merge_repoints_updates_and_drops_pair_internal_edge(db_session: Session):
    _make_task(db_session, 1)
    _make_task(db_session, 2)
    _make_task(db_session, 3)
    db_session.add(TaskUpdate(ts=T0, recorded_at=T0, task_id=2, actor_user_id=101,
                              kind="note", payload={"text": "x"}, created_from="marker"))
    db_session.add(TaskDependency(predecessor_task_id=2, successor_task_id=1,
                                   created_by_decision_id=1))  # pair-internal
    db_session.add(TaskDependency(predecessor_task_id=2, successor_task_id=3,
                                   created_by_decision_id=1))  # external, should redirect
    db_session.flush()

    merge_tasks(db_session, absorbed_id=2, survivor_id=1)

    updates = db_session.query(TaskUpdate).filter_by(task_id=1).all()
    assert len(updates) == 1

    pair_internal = db_session.get(TaskDependency, {"predecessor_task_id": 2, "successor_task_id": 1})
    assert pair_internal is None

    redirected = db_session.get(TaskDependency, {"predecessor_task_id": 1, "successor_task_id": 3})
    assert redirected is not None


def test_merge_aborts_on_cycle_g60(db_session: Session):
    _make_task(db_session, 1)
    _make_task(db_session, 2)
    _make_task(db_session, 3)
    # 3 -> 1 already exists; merging 2 into 1 while 2 -> 3 exists would create
    # a cycle 1 -> 3 -> 1 once 2's edges redirect onto 1.
    db_session.add(TaskDependency(predecessor_task_id=3, successor_task_id=1, created_by_decision_id=1))
    db_session.add(TaskDependency(predecessor_task_id=2, successor_task_id=3, created_by_decision_id=1))
    db_session.flush()

    with pytest.raises(DependencyCycleError):
        merge_tasks(db_session, absorbed_id=2, survivor_id=1)


# ---------------------------------------------------------------------------
# split — "compose", not a new op: ordinary facet ops through the fold
# ---------------------------------------------------------------------------


def test_split_creates_children_with_parent_link(db_session: Session):
    _make_task(db_session, 1)
    db_session.add(DomainEvent(
        ts=T0, kind="decision_effective", aggregate="decision", aggregate_id=1,
        payload={"decision_id": 1, "ops": [
            {"target": "task:2", "facet": "description", "op": "set", "value": "child A"},
            {"target": "task:2", "facet": "parent_task_id", "op": "set", "value": 1},
            {"target": "task:1", "facet": "description", "op": "set", "value": "refined parent"},
        ]},
    ))
    db_session.flush()
    TasksConsumer(db_session).poll_and_apply()

    child = db_session.get(Task, 2)
    parent = db_session.get(Task, 1)
    assert child.parent_task_id == 1
    assert parent.description == "refined parent"
    assert parent.status != "done"  # parent status is NEVER derived from children [EVM-014]


# ---------------------------------------------------------------------------
# TSK-5 — cross-project transfer (G59)
# ---------------------------------------------------------------------------


def test_transfer_moves_project_and_clears_teams(db_session: Session):
    _make_task(db_session, 1, project_id=10, project_kind=ProjectKind.PROGRAM)
    db_session.add(TaskTeam(task_id=1, team_id=5))
    db_session.flush()

    db_session.add(DomainEvent(
        ts=T0, kind="decision_effective", aggregate="decision", aggregate_id=1,
        payload={"decision_id": 1, "ops": [
            {"target": "task:1", "facet": "project", "op": "set",
             "value": {"project_id": 20, "project_kind": "campaign"}},
        ]},
    ))
    TasksConsumer(db_session).poll_and_apply()

    task = db_session.get(Task, 1)
    assert task.project_id == 20
    assert task.project_kind == "campaign"
    assert db_session.query(TaskTeam).filter_by(task_id=1).count() == 0


def test_transfer_flips_now_illegal_edges_to_needs_rewire_g51(db_session: Session):
    _make_task(db_session, 1, project_id=10, project_kind=ProjectKind.CAMPAIGN)
    _make_task(db_session, 2, project_id=11, project_kind=ProjectKind.PROGRAM)
    db_session.add(TaskDependency(predecessor_task_id=1, successor_task_id=2,
                                   created_by_decision_id=1, status="confirmed"))
    db_session.flush()

    # transfer task 1 into ANOTHER campaign project -> now campaign<->campaign,
    # which G51 never admits across different campaigns
    db_session.add(DomainEvent(
        ts=T0, kind="decision_effective", aggregate="decision", aggregate_id=2,
        payload={"decision_id": 2, "ops": [
            {"target": "task:2", "facet": "project", "op": "set",
             "value": {"project_id": 12, "project_kind": "campaign"}},
        ]},
    ))
    TasksConsumer(db_session).poll_and_apply()

    edge = db_session.get(TaskDependency, {"predecessor_task_id": 1, "successor_task_id": 2})
    assert edge.status == "needs_rewire"

"""Owner: B. TSK-3 — blocks-only DAG, cycle check at write, the G51 admission
matrix, and the requested/confirmed/needs_rewire lifecycle [EVM-006].
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import DependencyStatus, ProjectKind, TaskStatus
from evermind.tasks.models import Task, TaskDependency


class DependencyCycleError(Exception):
    def __init__(self, path: list[int]):
        self.path = path
        super().__init__(f"dependency cycle: {' -> '.join(map(str, path))}")


class DependencyNotAdmittedError(Exception):
    """G51 — campaign <-> a *different* campaign is never allowed."""


def _admitted(predecessor: Task, successor: Task) -> bool:
    if predecessor.project_id == successor.project_id:
        return True  # same project ✓
    both_campaigns = (
        predecessor.project_kind == ProjectKind.CAMPAIGN
        and successor.project_kind == ProjectKind.CAMPAIGN
    )
    return not both_campaigns  # campaign<->program ✓, program<->program ✓, campaign<->different-campaign ✗


def _has_path(session: Session, *, start: int, target: int) -> bool:
    """BFS over ALL existing edges (requested + confirmed — a cycle is a cycle
    regardless of confirmation status): is there a path start -> ... -> target?
    """
    seen: set[int] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        successors = session.scalars(
            select(TaskDependency.successor_task_id).where(
                TaskDependency.predecessor_task_id == current
            )
        )
        frontier.extend(successors)
    return False


def has_cycle_through(session: Session, task_id: int) -> bool:
    """Is there any path from `task_id` back to itself via >=1 edge? Used by
    TSK-4 merge (G60) after redirecting edges onto the survivor — `_has_path`
    alone can't answer this directly since `start == target` trivially "finds"
    itself at step zero.
    """
    successors = session.scalars(
        select(TaskDependency.successor_task_id).where(
            TaskDependency.predecessor_task_id == task_id
        )
    ).all()
    return any(_has_path(session, start=s, target=task_id) for s in successors)


def revalidate_edges_for_transfer(session: Session, task_id: int) -> list[TaskDependency]:
    """TSK-5 — after a cross-project transfer changes `task_id`'s
    `project_id`/`project_kind`, re-check every edge touching it against G51;
    violating edges flip to `needs_rewire` (never silently dropped or kept
    confirmed against a now-illegal pairing). Returns the edges that flipped.
    """
    task = session.get(Task, task_id)
    if task is None:
        raise LookupError(f"task {task_id} not found")
    edges = session.scalars(
        select(TaskDependency).where(
            (TaskDependency.predecessor_task_id == task_id)
            | (TaskDependency.successor_task_id == task_id)
        )
    ).all()
    flipped = []
    for edge in edges:
        other_id = (
            edge.successor_task_id if edge.predecessor_task_id == task_id
            else edge.predecessor_task_id
        )
        other = session.get(Task, other_id)
        if other is None:
            continue
        predecessor = task if edge.predecessor_task_id == task_id else other
        successor = other if edge.predecessor_task_id == task_id else task
        if not _admitted(predecessor, successor):
            edge.status = DependencyStatus.NEEDS_REWIRE
            flipped.append(edge)
    return flipped


def add_edge(session: Session, *, predecessor_id: int, successor_id: int, decision_id: int) -> None:
    predecessor = session.get(Task, predecessor_id)
    successor = session.get(Task, successor_id)
    if predecessor is None or successor is None:
        raise LookupError("both tasks must exist before a dependency edge is created")

    if not _admitted(predecessor, successor):
        raise DependencyNotAdmittedError(
            f"task {predecessor_id} (campaign {predecessor.project_id}) cannot depend across "
            f"to task {successor_id} (campaign {successor.project_id}) — G51"
        )

    # cycle check: adding predecessor->successor is a cycle iff successor can already reach predecessor
    if _has_path(session, start=successor_id, target=predecessor_id):
        raise DependencyCycleError([predecessor_id, successor_id])

    existing = session.get(TaskDependency, {
        "predecessor_task_id": predecessor_id, "successor_task_id": successor_id,
    })
    if existing is not None:
        return  # idempotent re-add
    session.add(TaskDependency(
        predecessor_task_id=predecessor_id, successor_task_id=successor_id,
        created_by_decision_id=decision_id, status=DependencyStatus.REQUESTED,
    ))


def confirm_edge(session: Session, *, predecessor_id: int, successor_id: int) -> None:
    edge = session.get(TaskDependency, {
        "predecessor_task_id": predecessor_id, "successor_task_id": successor_id,
    })
    if edge is None:
        raise LookupError("no such edge to confirm")
    edge.status = DependencyStatus.CONFIRMED


def remove_edge(session: Session, *, predecessor_id: int, successor_id: int) -> None:
    edge = session.get(TaskDependency, {
        "predecessor_task_id": predecessor_id, "successor_task_id": successor_id,
    })
    if edge is not None:
        session.delete(edge)


def on_predecessor_status_changed(session: Session, *, predecessor_id: int) -> None:
    """[EVM-006] only `done` satisfies a dependency; a canceled predecessor flips
    dependents' edges to `needs_rewire` — never silently "unblocked".
    """
    predecessor = session.get(Task, predecessor_id)
    if predecessor is None or predecessor.status != TaskStatus.CANCELED:
        return
    edges = session.scalars(
        select(TaskDependency).where(TaskDependency.predecessor_task_id == predecessor_id)
    )
    for edge in edges:
        edge.status = DependencyStatus.NEEDS_REWIRE

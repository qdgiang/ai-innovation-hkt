"""Owner: B. TSK-1 — pure fold logic: applies a decision's `ops` (the
design-v2.md §Facet registry vocabulary) onto the `tasks` projection.

Called only by `tasks/consumer.py` in response to a `decision_effective`
domain event — never by raw commands (architecture.md: "DERIVED — never
hand-edited").

Working assumptions pinned here because no producer exists yet (A's DEC-2
facet registry / ING-5 linkage land later); revisit if the real `ops` shape
A ships differs:
  - `target` is `"task:<id>"` for every task-scoped facet.
  - `assignment`/`team` `add`/`remove` carry a single id in `value`; `set`
    carries a `list[int]` (the full replacement roster).
  - `dependency` `add`/`remove` carries `{"successor_task_id": <id>}` in
    `value`, with `target` naming the predecessor.
  - `attr:<name>` on a task target has no dedicated column yet (only team/
    project-scope policy attrs are modeled today) — logged, not applied.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from evermind.contracts.enums import TaskStatus
from evermind.tasks import dependencies
from evermind.tasks.models import Task, TaskAssignment, TaskTeam

logger = logging.getLogger(__name__)

TASK_FIELD_FACETS = {
    "description", "status", "start_date", "end_date", "type", "kind",
    "parent_task_id",  # [EVM-014] split = compose: create children + refine
                       # parent via ordinary facet ops, design-v2.md is explicit
                       # this is "not a new op" — see tasks/merge.py's docstring.
}


def _task_id_from_target(target: str) -> int:
    kind, _, raw_id = target.partition(":")
    if kind != "task" or not raw_id:
        raise ValueError(f"expected a 'task:<id>' target, got {target!r}")
    return int(raw_id)


def _get_or_create_task(session: Session, task_id: int, project_id: int | None = None) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        # NEW_TASK path: the id is allocated by the caller (decisions.service,
        # which knows the group's project) — this fold just materializes the row.
        task = Task(
            id=task_id, project_id=project_id or 0, kind="project", description="",
        )
        session.add(task)
        # flush NOW: prod sessions run autoflush=False (db/session.py), so the
        # next op's `session.get` would miss this pending row and re-create it
        # (duplicate-PK crash on any multi-op NEW_TASK decision).
        session.flush()
    return task


def apply_op(session: Session, *, decision_id: int, op: dict) -> None:
    """Apply one `{target, facet, op, value}` entry. One decision's ops are
    applied all-or-nothing by the caller's transaction (DEC-9 multi-op).
    """
    target = op["target"]
    facet = op["facet"]
    verb = op["op"]
    value = op.get("value")

    if facet == "end_date":
        # TSK-7: campaign defaulting (project.end_date - 1 day) is computed
        # upstream by `decisions` (the only module allowed to read `org` for
        # project.kind/end_date) and handed down as either a plain value
        # (explicit human date -> clears the flag, design-v2 §Facet registry)
        # or {"value": ..., "end_date_defaulted": true} (an auto-default).
        task_id = _task_id_from_target(target)
        task = _get_or_create_task(session, task_id)
        if verb != "set":
            raise ValueError(f"facet 'end_date' only supports 'set', got {verb!r}")
        if isinstance(value, dict):
            task.end_date = value["value"]
            task.end_date_defaulted = bool(value.get("end_date_defaulted", False))
        else:
            task.end_date = value
            task.end_date_defaulted = False
        return

    if facet == "status":
        # `status` accepts either a plain value or the blocked-context dict
        # {"status": "blocked", "waiting_on_party_id"?, "waiting_on_text"?,
        # "since"?} — the write path the blocker board's counterparty grouping
        # needs (promotion submits this shape). Leaving the blocked state
        # clears the waiting-on context: it belongs to the blockage, not the task.
        task_id = _task_id_from_target(target)
        task = _get_or_create_task(session, task_id)
        if verb != "set":
            raise ValueError(f"facet 'status' only supports 'set', got {verb!r}")
        if isinstance(value, dict):
            task.status = TaskStatus(value["status"])
            task.blocked_waiting_on_party_id = value.get("waiting_on_party_id")
            task.blocked_waiting_on_text = value.get("waiting_on_text")
            since = value.get("since")
            task.blocked_since = (datetime.fromisoformat(since)
                                  if isinstance(since, str) else since)
        else:
            task.status = TaskStatus(value)
        if task.status != TaskStatus.BLOCKED:
            task.blocked_waiting_on_party_id = None
            task.blocked_waiting_on_text = None
            task.blocked_since = None
        return

    if facet in TASK_FIELD_FACETS:
        task_id = _task_id_from_target(target)
        task = _get_or_create_task(session, task_id)
        if verb != "set":
            raise ValueError(f"facet {facet!r} only supports 'set', got {verb!r}")
        setattr(task, facet, value)
        return

    if facet == "assignment":
        task_id = _task_id_from_target(target)
        _get_or_create_task(session, task_id)
        _apply_slot_op(session, TaskAssignment, task_id=task_id, verb=verb, value=value,
                        slot_field="user_id")
        return

    if facet == "team":
        task_id = _task_id_from_target(target)
        _get_or_create_task(session, task_id)
        _apply_slot_op(session, TaskTeam, task_id=task_id, verb=verb, value=value,
                        slot_field="team_id")
        return

    if facet == "project":
        # TSK-5 cross-project transfer (G59): the two-key authority check +
        # re-dating under the destination are decisions'/callers' job; this
        # fold's part is: move the row, clear its team membership (destination
        # re-teams via a following `team` op, else falls to project-level per
        # G48), and revalidate its dependency edges against G51 (violations ->
        # needs_rewire, never silently kept as if still valid).
        task_id = _task_id_from_target(target)
        task = _get_or_create_task(session, task_id)
        if verb != "set" or not isinstance(value, dict):
            raise ValueError("facet 'project' expects op='set' with a dict value")
        task.project_id = value["project_id"]
        task.project_kind = value["project_kind"]
        session.query(TaskTeam).filter_by(task_id=task_id).delete()
        session.flush()
        dependencies.revalidate_edges_for_transfer(session, task_id)
        return

    if facet == "note":
        task_id = _task_id_from_target(target)
        task = _get_or_create_task(session, task_id)
        if verb != "append":
            raise ValueError(f"facet 'note' only supports 'append', got {verb!r}")
        task.note = f"{task.note}\n{value}" if task.note else str(value)
        return

    if facet == "dependency":
        predecessor_id = _task_id_from_target(target)
        if not isinstance(value, dict):
            raise ValueError(f"facet 'dependency' expects a dict value, got {value!r}")
        successor_id = int(value["successor_task_id"])
        if verb == "add":
            dependencies.add_edge(session, predecessor_id=predecessor_id,
                                   successor_id=successor_id, decision_id=decision_id)
        elif verb == "remove":
            dependencies.remove_edge(session, predecessor_id=predecessor_id,
                                      successor_id=successor_id)
        else:
            raise ValueError(f"facet 'dependency' only supports add/remove, got {verb!r}")
        return

    if facet.startswith("attr:"):
        logger.info("op on facet %s not materialized by tasks fold (target=%s)", facet, target)
        return

    raise ValueError(f"unknown facet {facet!r}")


def apply_decision_ops(session: Session, *, decision_id: int, ops: list[dict]) -> list[int]:
    """Apply every op of one effective decision; returns the touched task ids
    (for TaskDecisionLog bookkeeping in the consumer).
    """
    touched: list[int] = []
    for op in ops:
        apply_op(session, decision_id=decision_id, op=op)
        target = op["target"]
        if target.startswith("task:"):
            touched.append(_task_id_from_target(target))
    return touched


def _apply_slot_op(session: Session, model, *, task_id: int, verb: str, value, slot_field: str) -> None:
    if verb == "add":
        exists = session.get(model, {"task_id": task_id, slot_field: value})
        if exists is None:
            session.add(model(task_id=task_id, **{slot_field: value}))
    elif verb == "remove":
        row = session.get(model, {"task_id": task_id, slot_field: value})
        if row is not None:
            session.delete(row)
    elif verb == "set":
        session.query(model).filter_by(task_id=task_id).delete()
        for slot_value in value:
            session.add(model(task_id=task_id, **{slot_field: slot_value}))
    else:
        raise ValueError(f"unsupported op {verb!r} for slot facet")

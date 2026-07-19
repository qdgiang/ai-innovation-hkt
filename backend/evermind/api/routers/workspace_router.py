"""Owner: A. GET /projects + GET /workspace/{project_id} — the composed bundle
the knowledge-base workspace UI renders from (frontend_ref shape: project,
members, tasks with lineage, decisions, evidence receipts with backlinks).

This is a BFF composition layer: it reads the projections other modules own
(tasks, decisions, org, messages) but never writes — writes stay on
`POST /commands`.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from evermind.api.deps import get_session, persona_user_id
from evermind.api.routers.decisions_router import _serialize
from evermind.connectors.models import Message
from evermind.contracts.enums import DecisionStatus, TaskStatus
from evermind.decisions.models import Decision, DecisionCitation
from evermind.org.models import ChatGroup, Team, User
from evermind.org.service import OrgService
from evermind.tasks.models import (
    Task, TaskAssignment, TaskDecisionLog, TaskDependency, TaskTeam, TaskUpdate,
)
from evermind.signals.service import SignalsService

router = APIRouter(tags=["workspace"])

ACTIVE_TASK_STATUSES = (TaskStatus.TODO, TaskStatus.DOING, TaskStatus.BLOCKED)


@router.get("/projects")
def list_projects(session: Session = Depends(get_session),
                  x_persona: str | None = Header(None)):
    """Phân-quyền spec 'View theo project': with a persona header the list is
    scoped to that user's projects (coordinator sees all). Header-less calls
    (curl/dev) keep the full list — the bundle endpoint is the hard gate."""
    from evermind.org.models import Project

    org = OrgService(session)
    viewer = org.get_user_by_handle(x_persona) if x_persona else None
    allowed = (set(org.project_ids_of_user(viewer.id))
               if viewer is not None and viewer.role_rank < 3 else None)

    counts = dict(session.execute(
        select(Task.project_id, func.count(Task.id)).group_by(Task.project_id)
    ).all())
    return [
        {"id": p.id, "name": p.name, "kind": p.kind.value, "status": p.status.value,
         "end_date": p.end_date, "task_count": counts.get(p.id, 0)}
        for p in session.scalars(select(Project).order_by(Project.id))
        if allowed is None or p.id in allowed
    ]


def _task_facts(log_rows: list[TaskDecisionLog]) -> dict[str, object]:
    """Fold attr:* ops last-write-wins in decision order — the 'current state
    facts' card. Ordering mirrors the projection fold: (ts, recorded_at, id)."""
    facts: dict[str, object] = {}
    for row in sorted(log_rows, key=lambda r: (r.ts, r.recorded_at, r.id)):
        if row.retracted:
            continue
        for op in row.ops:
            facet = op.get("facet", "")
            if facet.startswith("attr:"):
                facts[facet[5:]] = op.get("value")
    return facts


def _decision_project(decision: Decision, task_projects: dict[int, int],
                      team_projects: dict[int, int]) -> int | None:
    target = decision.scope_target or ""
    kind, _, raw = target.partition(":")
    if not raw.isdigit():
        return None
    ref = int(raw)
    if kind == "project":
        return ref
    if kind == "team":
        return team_projects.get(ref)
    if kind == "task":
        # unborn tasks (proposed NEW_TASK): fall back to the creation context
        return task_projects.get(ref, decision.context_project_id)
    return None


@router.get("/workspace/{project_id}")
def workspace(project_id: int, session: Session = Depends(get_session),
              viewer_id: int = Depends(persona_user_id)):
    org = OrgService(session)
    project = org.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="unknown project")
    # phân-quyền spec: view theo project — membership (any team) or coordinator
    if not org.can_view_project(viewer_id, project_id):
        raise HTTPException(status_code=403,
                            detail="persona is not a member of this project")

    tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)))
    task_ids = [t.id for t in tasks] or [-1]

    assignments = defaultdict(list)
    for row in session.scalars(select(TaskAssignment).where(TaskAssignment.task_id.in_(task_ids))):
        assignments[row.task_id].append(row.user_id)
    task_teams = defaultdict(list)
    for row in session.scalars(select(TaskTeam).where(TaskTeam.task_id.in_(task_ids))):
        task_teams[row.task_id].append(row.team_id)
    deps_out = defaultdict(list)   # predecessor -> successors it blocks
    deps_in = defaultdict(list)    # successor -> predecessors it waits on
    dep_rows = list(session.scalars(select(TaskDependency).where(
        TaskDependency.predecessor_task_id.in_(task_ids)
        | TaskDependency.successor_task_id.in_(task_ids))))
    for row in dep_rows:
        deps_out[row.predecessor_task_id].append(
            {"task_id": row.successor_task_id, "status": row.status.value})
        deps_in[row.successor_task_id].append(
            {"task_id": row.predecessor_task_id, "status": row.status.value})

    log_rows = defaultdict(list)
    for row in session.scalars(select(TaskDecisionLog).where(TaskDecisionLog.task_id.in_(task_ids))):
        log_rows[row.task_id].append(row)
    update_rows = list(session.scalars(
        select(TaskUpdate).where(TaskUpdate.task_id.in_(task_ids))
        .order_by(TaskUpdate.ts, TaskUpdate.id)))
    updates_by_task = defaultdict(list)
    for row in update_rows:
        updates_by_task[row.task_id].append(row)

    # ── decisions of this project (incl. proposed NEW_TASK whose task row does
    # not exist yet — target project unresolvable, kept for the single-project
    # demo posture) ─────────────────────────────────────────────────────────
    task_projects = dict(session.execute(select(Task.id, Task.project_id)).all())
    team_projects = dict(session.execute(select(Team.id, Team.project_id)).all())
    all_decisions = list(session.scalars(
        select(Decision).order_by(Decision.ts.desc(), Decision.id.desc())))
    decisions = []
    for d in all_decisions:
        proj = _decision_project(d, task_projects, team_projects)
        # unresolvable targets belong here ONLY when they are genuinely unborn
        # NEW_TASK proposals (stamped new_task_id) — anything else is an
        # orphaned row (e.g. test leftovers around a table wipe), not demo data
        if proj == project_id or (proj is None and d.new_task_id is not None):
            decisions.append(d)
    decision_ids = [d.id for d in decisions] or [-1]
    citations = defaultdict(list)
    for row in session.scalars(
        select(DecisionCitation).where(DecisionCitation.decision_id.in_(decision_ids))
    ):
        citations[row.decision_id].append(row)

    handles = {u.id: u.handle for u in org.list_personas()}
    serialized_decisions = [_serialize(d, citations.get(d.id, []), handles) for d in decisions]

    decision_ids_by_task = defaultdict(list)
    for d in decisions:
        kind, _, raw = (d.scope_target or "").partition(":")
        if kind == "task" and raw.isdigit():
            decision_ids_by_task[int(raw)].append(d.id)

    # ── evidence receipts: every message cited by a decision or anchoring a
    # task update, with typed backlinks ─────────────────────────────────────
    backlinks: dict[int, list[dict]] = defaultdict(list)
    for d in decisions:
        for c in citations.get(d.id, []):
            backlinks[c.message_id].append(
                {"type": "decision", "id": d.id, "label": d.description,
                 "role": c.kind.value})
    for row in update_rows:
        if row.source_message_id is not None:
            backlinks[row.source_message_id].append(
                {"type": "task", "id": row.task_id,
                 "label": f"{row.kind} update", "role": "reports"})

    message_ids = list(backlinks.keys()) or [-1]
    messages = list(session.scalars(select(Message).where(Message.id.in_(message_ids))))
    group_names = {g.id: g.platform_chat_id
                   for g in session.scalars(select(ChatGroup))}
    users_by_handle = {u.handle: u for u in session.scalars(select(User)) if u.handle}
    evidence = [
        {
            "message_id": m.id,
            "source": m.source,
            "channel": group_names.get(m.group_id),
            "author_identity": m.author_identity,
            "author_user_id": getattr(users_by_handle.get(m.author_identity), "id", None),
            "ts": m.ts,
            "text": m.text,
            "rev": m.current_rev,
            "thread_ref": m.thread_ref,
            "raw_ref": m.raw_ref,
            "backlinks": backlinks.get(m.id, []),
        }
        for m in sorted(messages, key=lambda m: m.id)
    ]

    # ── members: project personas with team roles and PIC load ──────────────
    teams = list(session.scalars(select(Team).where(Team.project_id == project_id)))
    pic_of = defaultdict(list)
    for task_id, user_ids in assignments.items():
        for uid in user_ids:
            pic_of[uid].append(task_id)
    members = []
    for user in org.list_personas():
        team_ids = org.teams_of_user(user.id)
        members.append({
            "id": user.id, "handle": user.handle, "name": user.name,
            "role_rank": user.role_rank, "status": user.status.value,
            "team_ids": team_ids,
            "leads_team_ids": org.teams_led_by(user.id),
            "pic_task_ids": sorted(pic_of.get(user.id, [])),
        })

    serialized_tasks = [
        {
            "id": t.id, "project_id": t.project_id, "kind": t.kind.value,
            "type": t.type.value, "description": t.description,
            "status": t.status.value, "merged_into": t.merged_into,
            "parent_task_id": t.parent_task_id,
            "start_date": t.start_date, "end_date": t.end_date,
            "end_date_defaulted": t.end_date_defaulted,
            "blocked_waiting_on_party_id": t.blocked_waiting_on_party_id,
            "blocked_waiting_on_text": t.blocked_waiting_on_text,
            "blocked_since": t.blocked_since, "note": t.note,
            "pics": assignments.get(t.id, []),
            "team_ids": task_teams.get(t.id, []),
            "blocks": deps_out.get(t.id, []),
            "waits_on": deps_in.get(t.id, []),
            "decision_ids": decision_ids_by_task.get(t.id, []),
            "facts": _task_facts(log_rows.get(t.id, [])),
            "update_count": len(updates_by_task.get(t.id, [])),
            "last_update_ts": (updates_by_task[t.id][-1].ts
                               if updates_by_task.get(t.id) else None),
        }
        for t in tasks
    ]

    blocked = [t for t in tasks if t.status == TaskStatus.BLOCKED]
    radar_lamps = SignalsService(session).radar_sweep(project_id=project_id)
    parties = {t.blocked_waiting_on_party_id: org.get_party(t.blocked_waiting_on_party_id)
               for t in blocked if t.blocked_waiting_on_party_id is not None}
    return {
        "project": {"id": project.id, "name": project.name,
                    "kind": project.kind.value, "status": project.status.value,
                    "end_date": project.end_date},
        "teams": [{"id": t.id, "name": t.name} for t in teams],
        "members": members,
        "tasks": serialized_tasks,
        "decisions": serialized_decisions,
        "evidence": evidence,
        "radar": {
            "confirmed_blockers": [{"task_id": t.id, "description": t.description,
                                    "since": t.blocked_since,
                                    "waiting_on": {"party_id": t.blocked_waiting_on_party_id,
                                                   "name": parties[t.blocked_waiting_on_party_id].name if t.blocked_waiting_on_party_id in parties and parties[t.blocked_waiting_on_party_id] else None,
                                                   "text": t.blocked_waiting_on_text}}
                                   for t in blocked],
            "lamps": [entry for entry in radar_lamps if entry["lamp"] != "blocked"],
        },
        "counts": {
            "tasks": len(tasks),
            "active_tasks": sum(1 for t in tasks if t.status in ACTIVE_TASK_STATUSES),
            "decisions": len(decisions),
            "superseded": sum(1 for d in decisions
                              if d.status == DecisionStatus.SUPERSEDED),
            "proposed": sum(1 for d in decisions
                            if d.status == DecisionStatus.PROPOSED),
            "blockers": len(blocked),
            "receipts": len(evidence),
        },
    }

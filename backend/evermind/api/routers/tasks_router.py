"""Owner: B. GET /tasks (DSH-4 filter matrix), /tasks/{id}/reasoning, /tasks/{id}/at
(TSK-8 time-travel)."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session
from evermind.tasks.service import TasksService

router = APIRouter(tags=["tasks"])


@router.get("/tasks")
def list_tasks(
    session: Session = Depends(get_session),
    project: int | None = None,
    team: int | None = None,
    status: str | None = None,
    pic: int | None = None,
    q: str | None = None,
):
    return TasksService(session).list_tasks(
        project_id=project, team_id=team, pic_user_id=pic,
        statuses=(status,) if status else None, description_contains=q,
    )


@router.get("/tasks/{task_id}/reasoning")
def task_reasoning(task_id: int, session: Session = Depends(get_session)):
    """Grounded summary + log (design-v2.md §Reasoning views). Citation badges
    and show-inactive need `decisions` (Lane A, not built) — see
    TasksService.reasoning_log's docstring.
    """
    return TasksService(session).reasoning_log(task_id)


@router.get("/tasks/{task_id}/at")
def task_at(task_id: int, ts: datetime, session: Session = Depends(get_session)):
    return TasksService(session).at(task_id, ts)

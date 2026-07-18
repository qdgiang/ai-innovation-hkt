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
    project: str | None = None,
    team: str | None = None,
    status: str | None = None,
    pic: str | None = None,
    type: str | None = None,
    q: str | None = None,
):
    """TODO(B): stakeholder filter matrix (time/PIC/team/status/type)."""
    raise NotImplementedError


@router.get("/tasks/{task_id}/reasoning")
def task_reasoning(task_id: int, session: Session = Depends(get_session)):
    """TODO(B): popup — grounded summary, log (maker/time/status), show-inactive,
    dual stamps, citation badges (design-v2.md §Reasoning views)."""
    raise NotImplementedError


@router.get("/tasks/{task_id}/at")
def task_at(task_id: int, ts: datetime, session: Session = Depends(get_session)):
    return TasksService(session).at(task_id, ts)

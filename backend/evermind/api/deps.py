"""Owner: A. Persona scoping — *who is asking*; *may they* stays domain
(architecture.md: "api does persona scoping only"). Settled #3, demo-honest:
the API trusts the persona header for scoping; real auth = T3 seam [EVM-001].
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from evermind.db.session import get_session  # noqa: F401  (re-exported for routers)
from evermind.decisions.service import DecisionsService
from evermind.org.service import OrgService


def persona(
    x_persona: str = Header(...),
    session: Session = Depends(get_session),
) -> str:
    """Validate the header names a seeded, non-departed user (by handle).
    No session/token — demo-honest, stated on the FE switcher (settled #3)."""
    org = OrgService(session)
    user = org.get_user_by_handle(x_persona)
    if user is None or user.status.value == "departed":
        raise HTTPException(status_code=400, detail=f"unknown persona {x_persona!r}")
    return x_persona


def persona_user_id(
    x_persona: str = Header(...),
    session: Session = Depends(get_session),
) -> int:
    """The validated persona's numeric user id — the wire persona is a HANDLE
    ("linh"), but projections key rows on user ids; routers that filter or
    stamp by id depend on THIS, never `int(persona)`."""
    org = OrgService(session)
    user = org.get_user_by_handle(x_persona)
    if user is None or user.status.value == "departed":
        raise HTTPException(status_code=400, detail=f"unknown persona {x_persona!r}")
    return user.id


def decisions_service(session: Session = Depends(get_session)) -> DecisionsService:
    """The universal gateway, wired with the org port and (interface #9) the
    tasks read port. B: implement `get_task_view(task_id) -> TaskView` on
    `tasks.service.TasksService` (shape: `contracts.ports.TaskView`); until it
    exists the gateway runs port-less (update-lane routing degrades to
    authority/confirm-card, G52 task checks are skipped)."""
    from evermind.tasks.service import TasksService  # api may import service ports

    tasks = TasksService(session)
    port = tasks if hasattr(tasks, "get_task_view") else None
    return DecisionsService(session, task_port=port)  # type: ignore[arg-type]

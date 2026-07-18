"""Owner: B. GET /blockers?by=party (SIG-2 board)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session
from evermind.tasks.service import TasksService

router = APIRouter(tags=["signals"])


@router.get("/blockers")
def list_blockers(by: str = "party", session: Session = Depends(get_session)):
    """Grouped-by-party board (G22/SIG-2). Party *names* aren't resolvable here
    (only `org` knows them, and `connectors`/`tasks` don't import it) — the FE
    resolves `party_id` -> display name via `org`'s own read surface.
    """
    blocked_tasks = TasksService(session).list_tasks(statuses=("blocked",))
    groups: dict[str, list[dict]] = {}
    for task in blocked_tasks:
        key = (
            f"party:{task.blocked_waiting_on_party_id}"
            if task.blocked_waiting_on_party_id is not None
            else task.blocked_waiting_on_text or "unspecified"
        )
        groups.setdefault(key, []).append({
            "task_id": task.id, "description": task.description, "since": task.blocked_since,
        })
    return groups

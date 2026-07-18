"""Owner: A. GET /decisions (DSH-4 filters + show_inactive)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session

router = APIRouter(tags=["decisions"])


@router.get("/decisions")
def list_decisions(
    session: Session = Depends(get_session),
    scope: str | None = None,
    q: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    user: str | None = None,
    show_inactive: bool = False,
):
    """TODO(A): filter matrix per architecture.md API sketch."""
    raise NotImplementedError

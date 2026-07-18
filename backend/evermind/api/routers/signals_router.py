"""Owner: B. GET /blockers?by=party (SIG-2 board)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session

router = APIRouter(tags=["signals"])


@router.get("/blockers")
def list_blockers(by: str = "party", session: Session = Depends(get_session)):
    """TODO(B): grouped-by-party board with age (radar SIG-3 output)."""
    raise NotImplementedError

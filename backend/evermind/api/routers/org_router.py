"""Owner: A. GET /personas — seeded users for the FE switcher."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session

router = APIRouter(tags=["org"])


@router.get("/personas")
def list_personas(session: Session = Depends(get_session)):
    """TODO(A): return seeded users (id, name, role_rank) for DSH-1's switcher."""
    raise NotImplementedError

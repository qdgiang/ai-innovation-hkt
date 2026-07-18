"""Owner: B. GET /feed, /inbox, /digest/{team}."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session, persona_user_id
from evermind.surfacing.service import SurfacingService

router = APIRouter(tags=["surfacing"])


@router.get("/feed")
def get_feed(session: Session = Depends(get_session), who_id: int = Depends(persona_user_id)):
    return SurfacingService(session).feed_for(who_id)


@router.get("/inbox")
def get_inbox(session: Session = Depends(get_session), who_id: int = Depends(persona_user_id)):
    return SurfacingService(session).inbox_for(who_id)


@router.get("/digest/{team}")
def get_digest(team: int, week: str | None = None, session: Session = Depends(get_session)):
    # TODO(B): `week` date-range scoping isn't implemented yet — digest_for
    # currently always reflects live state, not a specific past week.
    return SurfacingService(session).digest_for(team)

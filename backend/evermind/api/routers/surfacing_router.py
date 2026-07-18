"""Owner: B. GET /feed, /inbox, /digest/{team}."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session, persona
from evermind.surfacing.service import SurfacingService

router = APIRouter(tags=["surfacing"])


@router.get("/feed")
def get_feed(session: Session = Depends(get_session), who: str = Depends(persona)):
    return SurfacingService(session).feed_for(int(who))


@router.get("/inbox")
def get_inbox(session: Session = Depends(get_session), who: str = Depends(persona)):
    return SurfacingService(session).inbox_for(int(who))


@router.get("/digest/{team}")
def get_digest(team: int, week: str, session: Session = Depends(get_session)):
    return SurfacingService(session).digest_for(team, week)

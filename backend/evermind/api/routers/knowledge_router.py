"""Owner: A. POST /qa — KNW-2 {question, persona} -> cited answer (DSH-6 box)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from evermind.api.deps import get_session, persona
from evermind.knowledge.service import KnowledgeService

router = APIRouter(tags=["knowledge"])


class QARequest(BaseModel):
    question: str


@router.post("/qa")
def ask(body: QARequest, session: Session = Depends(get_session), who: str = Depends(persona)):
    """KNW-2: {question, persona} → cited, truth-state-labeled answer (DSH-6)."""
    return KnowledgeService(session).answer(body.question, who)

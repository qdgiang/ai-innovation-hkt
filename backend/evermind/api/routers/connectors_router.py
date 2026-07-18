"""Owner: B. GET /health/capture (CAP-5 banners), POST /uploads/transcript (CAP-3)."""
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from evermind.api.deps import get_session, persona
from evermind.connectors.health import CaptureHealthService
from evermind.connectors.transcript import TranscriptConnector

router = APIRouter(tags=["connectors"])


@router.get("/health/capture")
def capture_health(session: Session = Depends(get_session)):
    return CaptureHealthService(session).check_all_groups()


@router.post("/uploads/transcript")
async def upload_transcript(
    file: UploadFile, session: Session = Depends(get_session), who: str = Depends(persona)
):
    content = (await file.read()).decode("utf-8")
    upload_id = TranscriptConnector(session).upload(
        filename=file.filename or "upload.txt", content=content, uploaded_by=int(who)
    )
    return {"upload_id": upload_id}

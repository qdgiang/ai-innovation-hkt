"""Owner: B. GET /health/capture (CAP-5 banners), POST /uploads/transcript (CAP-3)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from evermind.api.deps import get_session, persona
from evermind.connectors.health import CaptureHealthService
from evermind.connectors.transcript import TranscriptConnector, UnsupportedTranscriptType

router = APIRouter(tags=["connectors"])


@router.get("/health/capture")
def capture_health(session: Session = Depends(get_session)):
    return CaptureHealthService(session).check_all_groups()


@router.post("/uploads/transcript")
async def upload_transcript(
    file: UploadFile, session: Session = Depends(get_session), who: str = Depends(persona)
):
    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=415, detail="transcript must be UTF-8 text — .txt/.md only [EVM-011]"
        ) from exc
    try:
        upload_id = TranscriptConnector(session).upload(
            filename=file.filename or "upload.txt", content=content, uploaded_by=int(who)
        )
    except UnsupportedTranscriptType as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    return {"upload_id": upload_id}

"""Owner: A. Manual extraction trigger — the demo's "extract now" button.

`POST /ingestion/extract` runs the exact beat the scheduler runs every
`EXTRACTION_INTERVAL_SEC`; `?group_id=` narrows to one group. Job logic lives
in `ingestion.service` (this router, like the scheduler, only calls the port).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evermind.api.deps import get_session, persona
from evermind.ingestion.service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/extract")
def extract_now(group_id: int | None = None,
                session: Session = Depends(get_session),
                who: str = Depends(persona)) -> dict:
    service = IngestionService(session)
    if group_id is not None:
        outcome = service.run_window(group_id)
        results = [outcome] if outcome is not None else []
    else:
        results = service.run_pending_windows()
    return {"triggered_by": who, "results": results}

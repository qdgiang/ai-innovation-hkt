"""Owner: A. App assembly — architecture.md §API surface. Module routers stay
with their owning module; this file only mounts them + the `POST /commands`
front door (kept literal on purpose: no business logic may grow here).
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from evermind.api.deps import decisions_service, persona
from evermind.api.routers import (
    connectors_router,
    decisions_router,
    knowledge_router,
    org_router,
    signals_router,
    surfacing_router,
    tasks_router,
    workspace_router,
)
from evermind.config import settings
from evermind.contracts.commands import Command
from evermind.decisions.service import DecisionsService

logger = logging.getLogger(__name__)


def _run_consumers_once() -> int:
    """One D3 read-side beat: fold pending `domain_events` into the tasks +
    surfacing projections. Also invoked by CLIs (demo seed) between commands."""
    from evermind.db.session import SessionLocal
    from evermind.surfacing.consumer import SurfacingConsumer
    from evermind.tasks.consumer import TasksConsumer

    with SessionLocal() as session:
        folded = TasksConsumer(session).poll_and_apply()
        folded += SurfacingConsumer(session).poll_and_apply()
        session.commit()
    return folded


@asynccontextmanager
async def lifespan(app: FastAPI):
    """P4 glue: the projection-consumer loop + the APScheduler jobs, started
    with the app (previously defined but never wired — runbook §3)."""
    stop = threading.Event()

    def consumer_loop() -> None:
        while not stop.is_set():
            try:
                _run_consumers_once()
            except Exception:  # keep the loop alive — a bad event never kills reads
                logger.exception("projection consumer beat failed")
            stop.wait(settings.consumer_poll_ms / 1000)

    thread: threading.Thread | None = None
    if settings.consumer_poll_ms > 0:
        thread = threading.Thread(target=consumer_loop, name="projection-consumers",
                                  daemon=True)
        thread.start()

    scheduler = None
    if settings.run_scheduler:
        from evermind.db.session import SessionLocal
        from evermind.scheduler.jobs import build_scheduler

        scheduler = build_scheduler(SessionLocal)
        scheduler.start()

    yield

    stop.set()
    if thread is not None:
        thread.join(timeout=5)
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="EverMind API", lifespan=lifespan)

# The dashboard calls the API straight from the browser (persona switcher,
# approve/reject taps, /qa) — split-origin FE (Vercel/ngrok demo shape).
# Demo-honest per settled #3: no cookies/credentials ride requests
# (allow_credentials stays False), the persona header is explicit. Tighten
# origins when real auth lands (T3).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(org_router.router)
app.include_router(decisions_router.router)
app.include_router(tasks_router.router)
app.include_router(signals_router.router)
app.include_router(surfacing_router.router)
app.include_router(connectors_router.router)
app.include_router(knowledge_router.router)
app.include_router(workspace_router.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/commands")
def post_command(
    command: Command,
    service: DecisionsService = Depends(decisions_service),
    who: str = Depends(persona),
):
    """The single write path for every surface (D3). Validates + persona-stamps,
    hands straight to the domain — see architecture.md §The write pipeline.
    [EVM-021]: a `version_conflict` outcome renders as HTTP 409 + diff card.
    """
    if command.persona != who:
        command = command.model_copy(update={"persona": who})  # persona-stamp
    outcome = service.handle(command)
    if outcome.get("status") == "version_conflict":
        raise HTTPException(status_code=409, detail=outcome)
    return outcome

"""FastAPI skeleton. Real endpoints (POST /ingest/messages, GET /records,
GET /digest, POST /ask, POST /telegram/webhook) land in Phase 2 — Phase 1 runs
the pipeline via CLI per ai-docs/plan.md.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="EverMind API", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": app.version}

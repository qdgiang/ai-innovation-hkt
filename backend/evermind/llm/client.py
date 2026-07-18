"""Owner: A. OpenAI-compatible gateway (architecture.md §LLM gateway).

STUB — P2 deliverable. Provider is env config only (`AI_BASE_URL`/`AI_MODEL`/
`AI_API_KEY`), never an import. No prompts live here — callers (`ingestion`,
`knowledge`) own prompts; this module only does the call, retry, and schema
validation.
"""
from __future__ import annotations

from pydantic import BaseModel


class LLMCallResult(BaseModel):
    window_id: int | None = None
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    validation_attempts: int


class LLMGateway:
    def call_json(self, *, system: str, user: str, schema: type[BaseModel]) -> tuple[BaseModel, LLMCallResult]:
        """TODO(A): retry-with-backoff on 429/503; validate against `schema`, retry once
        with the validation error appended, then raise (window stays pending + backlog
        notice — never half-persisted). Every call logs window id/model/tokens/latency.
        """
        raise NotImplementedError

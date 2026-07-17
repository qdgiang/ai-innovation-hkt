"""F4 — passive LLM extraction (Phase 1).

Pure function: conversation window in -> ExtractedRecords out. No DB writes, no
platform awareness, no persistence — the backend owns all of that. The LLM client
is provider-agnostic (OpenAI-compatible SDK; AI_BASE_URL / AI_MODEL env config).
"""

from __future__ import annotations

from collections.abc import Sequence

from ai.schemas import ExtractedRecord, Message


def extract_records(window: Sequence[Message]) -> list[ExtractedRecord]:
    """Extract decision/blocker/status records from one conversation window."""
    raise NotImplementedError("Phase 1 (F4)")

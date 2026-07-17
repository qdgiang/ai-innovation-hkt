"""F8 — cited Q&A (Phase 1 minimal, Phase 2+ full).

Pure function: records + question in -> cited answer out. Retrieval starts as
keyword/SQL over records (backend supplies candidates); embeddings only if that
demonstrably misses (plan.md Phase 4 #6).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from ai.schemas import Message, Record


class CitedAnswer(BaseModel):
    answer: str
    record_ids: list[str]
    message_ids: list[str]


def answer_question(
    question: str, candidates: Sequence[Record], sources: Sequence[Message]
) -> CitedAnswer:
    raise NotImplementedError("Phase 1 (F8 minimal)")

"""Owner: A. Retrieval + truth-state Q&A (architecture.md §Knowledge module & RAG posture).

STUB — P5 deliverable (KNW-1/2). Structured-first retrieval (typed SQL over
decisions/tasks/signals/parties); pgvector (KNW-3) only if keyword retrieval
measurably misses. LangChain lives ONLY in this module.
"""
from __future__ import annotations

from sqlalchemy.orm import Session


class KnowledgeService:
    def __init__(self, session: Session):
        self.session = session

    def answer(self, question: str, persona: str) -> dict:
        """TODO(A): KNW-2 — truth-state filter (superseded->current-with-note,
        proposed->pending-labeled, window->date-aware [EVM-007]); mandatory
        per-line citations + citation-completeness post-check.
        """
        raise NotImplementedError

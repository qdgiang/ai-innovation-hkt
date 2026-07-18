"""Owner: A. Retrieval + truth-state Q&A (architecture.md §Knowledge module & RAG posture).

KNW-1/2: structured-first retrieval — typed SQL over decisions/tasks/messages,
keyword-scored; the LLM only *composes* the answer from retrieved rows, it never
recalls facts on its own. Truth-state filter: superseded rows are labeled with
their successor, proposed rows are labeled pending, windowed rows carry their
dates ([EVM-007]). Degrades to a structured-only answer when the LLM gateway is
unavailable — the citations are the product, not the prose.
"""
from __future__ import annotations

import re

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message
from evermind.contracts.enums import DecisionStatus
from evermind.decisions.models import Decision, DecisionCitation
from evermind.llm.client import LLMGateway, LLMUnavailable
from evermind.org.service import OrgService
from evermind.tasks.models import Task

_WORD = re.compile(r"[\wàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
                   r"ùúủũụưừứửữựỳýỷỹỵđ]+", re.IGNORECASE | re.UNICODE)

SYSTEM_PROMPT = """You are EverMind, the organizational memory of a volunteer NPO.
Answer the user's question **in the same language as the question** (usually Vietnamese).
Rules:
- Use ONLY the facts in the provided context rows. If the context cannot answer, say so.
- Cite every claim inline with the row markers you used: [D<id>] for decisions, [T<id>] for tasks, [m<id>] for chat messages.
- Truth-state discipline: rows labeled `superseded` are NOT current — mention them only as history and name the successor; rows labeled `proposed` are pending approval, never state them as fact; rows with an effect window apply only inside those dates.
- Be concise: 2-5 sentences."""


class QAAnswer(BaseModel):
    answer: str
    cited_decision_ids: list[int] = []
    cited_task_ids: list[int] = []
    cited_message_ids: list[int] = []


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if len(w) >= 3}


def _score(tokens: set[str], *fields: str | None) -> int:
    haystack = " ".join(f for f in fields if f).lower()
    return sum(1 for t in tokens if t in haystack)


class KnowledgeService:
    def __init__(self, session: Session, gateway: LLMGateway | None = None):
        self.session = session
        self.gateway = gateway or LLMGateway()

    # ── retrieval (KNW-1) ────────────────────────────────────────────────

    def _decision_line(self, decision: Decision, handles: dict[int, str | None],
                       message_ids: list[int]) -> str:
        state = decision.status.value
        if decision.status is DecisionStatus.SUPERSEDED and decision.superseded_by_decision_id:
            state += f" — replaced by D{decision.superseded_by_decision_id}"
        if decision.status is DecisionStatus.REJECTED and decision.rejected_reason:
            state += f" ({decision.rejected_reason.value})"
        window = ""
        if decision.effect_window_from is not None:
            window = (f" [effect window {decision.effect_window_from.date()} → "
                      f"{decision.effect_window_until.date() if decision.effect_window_until else '…'}]")
        maker = handles.get(decision.decided_by_user_id) or f"user#{decision.decided_by_user_id}"
        cites = " ".join(f"[m{mid}]" for mid in message_ids)
        extra = f" | context: {decision.context}" if decision.context else ""
        return (f"[D{decision.id}] ({state}){window} {decision.description} — decided by "
                f"@{maker} on {decision.ts.date()} {cites}{extra}")

    def retrieve(self, question: str) -> dict:
        tokens = _tokens(question)
        handles = {u.id: u.handle for u in OrgService(self.session).list_personas()}

        decisions = list(self.session.scalars(select(Decision)))
        scored_d = sorted(
            ((d, _score(tokens, d.description, d.context, d.note)) for d in decisions),
            key=lambda pair: pair[1], reverse=True,
        )
        top_decisions = [d for d, s in scored_d if s > 0][:8]

        tasks = list(self.session.scalars(select(Task)))
        scored_t = sorted(
            ((t, _score(tokens, t.description, t.note)) for t in tasks),
            key=lambda pair: pair[1], reverse=True,
        )
        top_tasks = [t for t, s in scored_t if s > 0][:6]

        cited_ids: dict[int, list[int]] = {}
        if top_decisions:
            rows = self.session.scalars(select(DecisionCitation).where(
                DecisionCitation.decision_id.in_([d.id for d in top_decisions])))
            for row in rows:
                cited_ids.setdefault(row.decision_id, []).append(row.message_id)

        lines: list[str] = [
            self._decision_line(d, handles, sorted(set(cited_ids.get(d.id, []))))
            for d in top_decisions
        ]
        for task in top_tasks:
            blocked = (f" — BLOCKED waiting on {task.blocked_waiting_on_text or 'a party'}"
                       f" since {task.blocked_since.date()}" if task.blocked_since else "")
            lines.append(f"[T{task.id}] (status {task.status}) {task.description}{blocked}")

        # ground the cited chat messages verbatim — the receipts
        message_ids = sorted({mid for ids in cited_ids.values() for mid in ids})
        if message_ids:
            for message in self.session.scalars(
                    select(Message).where(Message.id.in_(message_ids)).order_by(Message.id)):
                lines.append(f"[m{message.id}] @{message.author_identity} "
                             f"({message.ts.date()}): {message.text}")
        return {"lines": lines, "decision_ids": [d.id for d in top_decisions],
                "task_ids": [t.id for t in top_tasks], "message_ids": message_ids,
                # wire-compat shape (PR #45 contract tests): per-decision receipts
                "citations": [
                    {"decision_id": d.id,
                     "message_ids": sorted(set(cited_ids.get(d.id, [])))}
                    for d in top_decisions
                ]}

    # ── the answer (KNW-2) ───────────────────────────────────────────────

    def answer(self, question: str, persona: str) -> dict:
        retrieved = self.retrieve(question)
        if not retrieved["lines"]:
            return {"answer": "Chưa có dữ liệu nào khớp với câu hỏi này trong bộ nhớ tổ chức.",
                    "sources": [], "llm": False, "citations": [],
                    "cited_decision_ids": [], "cited_task_ids": [], "cited_message_ids": []}

        context = "\n".join(retrieved["lines"])
        try:
            parsed, _meta = self.gateway.call_json(
                system=SYSTEM_PROMPT,
                user=(f"Persona asking: @{persona}\n\nContext rows:\n{context}\n\n"
                      f"Question: {question}\n\n"
                      'Reply as JSON: {"answer": "...", "cited_decision_ids": [..], '
                      '"cited_task_ids": [..], "cited_message_ids": [..]}'),
                schema=QAAnswer,
            )
            assert isinstance(parsed, QAAnswer)
            return {"answer": parsed.answer, "sources": retrieved["lines"], "llm": True,
                    "citations": retrieved["citations"],
                    "cited_decision_ids": parsed.cited_decision_ids,
                    "cited_task_ids": parsed.cited_task_ids,
                    "cited_message_ids": parsed.cited_message_ids}
        except LLMUnavailable:
            # structured-only fallback: the retrieved truth-state rows ARE an answer
            return {"answer": "LLM không khả dụng — dưới đây là các bản ghi khớp nhất "
                              "(đã gắn nhãn trạng thái):\n" + context,
                    "sources": retrieved["lines"], "llm": False,
                    "citations": retrieved["citations"],
                    "cited_decision_ids": retrieved["decision_ids"],
                    "cited_task_ids": retrieved["task_ids"],
                    "cited_message_ids": retrieved["message_ids"]}

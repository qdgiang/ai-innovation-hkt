"""Owner: A. ING-4 — LLM extraction: output schema, prompt, candidate→command
mapping. The LLM only DRAFTS: every candidate still enters through the command
gateway, where confidence (τ, `CONFIDENCE_TAU`) and the authority gate decide
proposed vs effective — extraction never writes domain state directly, exactly
like the demo seeder it replaces.

No provider code lives here: `llm.client.LLMGateway` is env-configured
(`AI_BASE_URL`/`AI_MODEL`/`AI_API_KEY` — DeepSeek today). No prompts live in
`llm` either (its module contract) — they live HERE, with their caller.
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from evermind.connectors.models import Message
from evermind.contracts.commands import (
    CitationSpec, OpSpec, ProposeDecision, RecordTaskUpdate,
)
from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionScope
from evermind.org.models import ChatGroup, Party, User
from evermind.tasks.models import Task


class ExtractedCandidate(BaseModel):
    kind: Literal["decision", "new_task", "task_update"]
    description: str
    status: Literal["todo", "doing", "done", "blocked"] | None = None
    task_id: int | None = None  # task_update only — must be an OPEN TASKS id
    decided_by_message_id: int  # the message whose author made the call
    evidence_message_ids: list[int] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedSignal(BaseModel):
    """SIG-1 weak signal — a MENTION, not a settled call. One row per voiced
    mention; the ledger accumulates them and promotion decides later
    (≥2 corroborating or 1 + staleness). Never gated on confidence: the whole
    point is catching things too weak to be decisions."""

    kind: Literal["blocker", "dependency", "ask", "parked"]
    topic: str  # short stable phrase — same wording for the same underlying issue
    excerpt: str
    message_id: int  # the mention's message (must exist in the window)
    task_id: int | None = None  # an OPEN TASKS id when clearly about that task
    party: str | None = None  # counterparty NAME from the ĐỐI TÁC list, if any


class ExtractionResult(BaseModel):
    candidates: list[ExtractedCandidate] = []
    signals: list[ExtractedSignal] = []


SYSTEM_PROMPT = """Bạn là EverMind — bộ nhớ tổ chức của một nhóm tình nguyện Việt Nam.
Nhiệm vụ: đọc một cửa sổ tin nhắn nhóm chat và trích xuất các QUYẾT ĐỊNH và
CÔNG VIỆC đã được chốt rõ ràng.

Trả về DUY NHẤT một JSON object đúng schema sau (không văn xuôi, không code fence):
{"candidates": [{"kind": "decision" | "new_task" | "task_update",
  "description": "<mô tả ngắn gọn, tiếng Việt>",
  "status": "todo" | "doing" | "done" | "blocked" | null,
  "task_id": <int hoặc null>,
  "decided_by_message_id": <int>,
  "evidence_message_ids": [<int>, ...],
  "confidence": <0.0-1.0>}],
 "signals": [{"kind": "blocker" | "dependency" | "ask" | "parked",
  "topic": "<cụm từ ngắn, ổn định — cùng một vấn đề thì dùng cùng một topic>",
  "excerpt": "<trích nguyên văn ngắn>",
  "message_id": <int>,
  "task_id": <int hoặc null>,
  "party": "<tên đối tác trong danh sách ĐỐI TÁC, hoặc null>"}]}

Quy tắc cho "candidates":
- CHỈ trích xuất khi có sự chốt/đồng thuận RÕ RÀNG trong tin nhắn. Câu hỏi,
  bàn luận chưa ngã ngũ, ý định mơ hồ → KHÔNG trích xuất.
- "decision": một quyết định được chốt (chọn phương án, chốt địa điểm/giá/kế hoạch).
- "new_task": việc mới được giao hoặc nhận làm. status = "blocked" nếu tin nhắn
  nói rõ đang vướng; ngược lại để null.
- "task_update": thay đổi trạng thái của một task trong danh sách OPEN TASKS —
  dùng ĐÚNG task_id từ danh sách đó; không khớp task nào → dùng new_task hoặc bỏ qua.
- decided_by_message_id: id tin nhắn của NGƯỜI chốt việc/quyết định.
- evidence_message_ids: mọi id tin nhắn làm bằng chứng — chỉ dùng id có thật
  trong cửa sổ, tuyệt đối không bịa.
- confidence: mức chắc chắn thật của bạn; >= 0.9 chỉ khi chốt rành mạch không thể hiểu khác.

Quy tắc cho "signals" (TÍN HIỆU YẾU — nhắc đến nhưng CHƯA chốt):
- "blocker": việc đang vướng/chờ ai đó mà KHÔNG có chốt rõ (vd "bên X vẫn chưa
  trả lời", "vẫn kẹt vụ giấy tờ"). Một lần nhắc = một signal — kể cả nói lướt qua.
- "dependency": việc phải chờ việc/bên khác xong mới làm được.
- "ask": câu hỏi cần quyết mà KHÔNG AI trả lời trong cửa sổ.
- "parked": chủ đề bị hoãn kiểu "để sau đi", "gần ngày rồi tính".
- topic: cụm ngắn gọn ổn định (vd "xưởng in chưa báo giá") — các lần nhắc cùng
  vấn đề phải ra cùng topic để hệ thống dồn tích được.
- party: chỉ dùng ĐÚNG tên trong danh sách ĐỐI TÁC; không khớp → null.
- message_id: id tin nhắn CÓ THẬT chứa lời nhắc — không bịa.
- KHÔNG tạo signal cho việc đã thành candidate (đã chốt thì không còn là tín hiệu yếu).

Chung:
- Tin nhắn bắt đầu bằng "!decision" hoặc "!blocked" đã được hệ thống xử lý riêng — BỎ QUA.
- Không có gì đạt chuẩn → {"candidates": [], "signals": []}.
"""


def build_user_prompt(messages: list[Message], *, members: list[User],
                      open_tasks: list[Task], parties: list[Party]) -> str:
    member_lines = "\n".join(
        f"- {u.handle or u.name}: {u.name}"
        + (" (coordinator)" if u.role_rank == 3 else " (lead)" if u.role_rank == 2 else "")
        for u in members
    ) or "- (chưa rõ)"
    task_lines = "\n".join(
        f"- task_id={t.id} [{t.status.value}] {t.description}" for t in open_tasks
    ) or "- (không có)"
    party_lines = "\n".join(
        f"- {p.name}" + (f" (còn gọi: {', '.join(p.aliases)})" if p.aliases else "")
        for p in parties
    ) or "- (không có)"
    message_lines = "\n".join(
        f"[{m.id}] {m.ts:%Y-%m-%d %H:%M} {m.author_identity}: {m.text}"
        for m in messages if m.text.strip()
    )
    return (
        f"THÀNH VIÊN:\n{member_lines}\n\n"
        f"OPEN TASKS (chỉ dùng các task_id này cho task_update):\n{task_lines}\n\n"
        f"ĐỐI TÁC / BÊN NGOÀI:\n{party_lines}\n\n"
        f"TIN NHẮN (cửa sổ cần trích xuất):\n{message_lines}"
    )


def command_id(group_id: int, from_epoch: int, to_epoch: int, index: int) -> uuid.UUID:
    """Deterministic per (window range, candidate) — a re-run of the same window
    replays recorded outcomes at the gateway instead of duplicating [EVM-021]."""
    return uuid.uuid5(uuid.NAMESPACE_URL,
                      f"evermind-extract:{group_id}:{from_epoch}:{to_epoch}:{index}")


def signal_command_id(group_id: int, from_epoch: int, to_epoch: int, index: int) -> uuid.UUID:
    """Same [EVM-021] idempotency for the signal lane — its own namespace so a
    window's Nth signal never collides with its Nth candidate."""
    return uuid.uuid5(uuid.NAMESPACE_URL,
                      f"evermind-signal:{group_id}:{from_epoch}:{to_epoch}:{index}")


def candidate_unit_key(candidate: ExtractedCandidate) -> str:
    """Materialization dedup key. Unlike the marker lane (one message = one
    task), one anchor message can legitimately decide SEVERAL new tasks — the
    description is part of the key so siblings don't dedup each other, while a
    re-extraction of the same window still does."""
    if candidate.kind == "task_update":
        return f"task:{candidate.task_id}|status"
    return f"NEW_TASK|{candidate.description}"


def candidate_to_command(
    candidate: ExtractedCandidate, *, index: int, group: ChatGroup,
    author: User, anchor: Message, window_id: int,
    from_epoch: int, to_epoch: int, messages_by_id: dict[int, Message],
) -> ProposeDecision | RecordTaskUpdate:
    cid = command_id(group.id, from_epoch, to_epoch, index)
    persona = author.handle or anchor.author_identity
    if candidate.kind == "task_update":
        return RecordTaskUpdate(
            client_command_id=cid, persona=persona, created_from=CreatedFrom.LLM,
            confidence=candidate.confidence, ts=anchor.ts, window_id=window_id,
            source_message_id=anchor.id, task_id=candidate.task_id or 0,
            actor_user_id=author.id, update_kind="status",
            payload={"status": candidate.status or "done"},
        )
    ops = [OpSpec(target="NEW_TASK", facet="description", op="set",
                  value=candidate.description)]
    if candidate.status == "blocked":
        ops.append(OpSpec(target="NEW_TASK", facet="status", op="set", value="blocked"))
    citations = [
        CitationSpec(message_id=mid, kind=CitationKind.EVIDENCE,
                     rev_at_capture=messages_by_id[mid].current_rev)
        for mid in candidate.evidence_message_ids
    ]
    return ProposeDecision(
        client_command_id=cid, persona=persona, created_from=CreatedFrom.LLM,
        confidence=candidate.confidence, ts=anchor.ts, window_id=window_id,
        source_message_id=anchor.id, decided_by_user_id=author.id,
        scope=DecisionScope.TASK, scope_target="NEW_TASK",
        description=candidate.description, ops=ops, citations=citations,
        context_group_id=group.id,
    )

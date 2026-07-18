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

from pydantic import BaseModel, Field, model_validator

from evermind.connectors.models import Message
from evermind.contracts.commands import (
    CitationSpec, OpSpec, ProposeDecision, RecordTaskUpdate,
)
from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionScope
from evermind.org.models import ChatGroup, Party, User
from evermind.tasks.models import Task


class ExtractedCandidate(BaseModel):
    kind: Literal["decision", "new_task", "task_update", "task_assignment"]
    description: str
    status: Literal["todo", "doing", "done", "blocked"] | None = None
    task_id: int | None = None  # task_update only — must be an OPEN TASKS id
    assignee_user_ids: list[int] = Field(default_factory=list)
    # The model must explicitly signal self-assignment; the service still
    # verifies that it is the anchor author's own internal id.
    self_assignment: bool = False
    decided_by_message_id: int  # the message whose author made the call
    evidence_message_ids: list[int] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def assignment_shape_is_valid(self):
        if self.kind == "task_assignment" and (self.task_id is None or not self.assignee_user_ids):
            raise ValueError("task_assignment requires task_id and assignee_user_ids")
        if self.assignee_user_ids and self.kind not in ("new_task", "task_assignment"):
            raise ValueError("assignee_user_ids are only valid for task assignments")
        if self.self_assignment and self.kind not in ("new_task", "task_assignment"):
            raise ValueError("self_assignment is only valid for task assignments")
        if self.self_assignment and not self.assignee_user_ids:
            raise ValueError("self_assignment requires assignee_user_ids")
        return self


class ExtractionResult(BaseModel):
    candidates: list[ExtractedCandidate] = []


SYSTEM_PROMPT = """Bạn là EverMind — bộ nhớ tổ chức của một nhóm tình nguyện Việt Nam.
Nhiệm vụ: đọc một cửa sổ tin nhắn nhóm chat và trích xuất các QUYẾT ĐỊNH và
CÔNG VIỆC đã được chốt rõ ràng.

Trả về DUY NHẤT một JSON object đúng schema sau (không văn xuôi, không code fence):
{"candidates": [{"kind": "decision" | "new_task" | "task_update" | "task_assignment",
  "description": "<mô tả ngắn gọn, tiếng Việt>",
  "status": "todo" | "doing" | "done" | "blocked" | null,
  "task_id": <int hoặc null>,
  "assignee_user_ids": [<internal user_id>, ...],
  "self_assignment": true | false,
  "decided_by_message_id": <int>,
  "evidence_message_ids": [<int>, ...],
  "confidence": <0.0-1.0>}]}

Quy tắc:
- CHỈ trích xuất khi có sự chốt/đồng thuận RÕ RÀNG trong tin nhắn. Câu hỏi,
  bàn luận chưa ngã ngũ, ý định mơ hồ → KHÔNG trích xuất.
- "decision": một quyết định được chốt (chọn phương án, chốt địa điểm/giá/kế hoạch).
- "new_task": việc mới được giao hoặc nhận làm. status = "blocked" nếu tin nhắn
  nói rõ đang vướng; ngược lại để null.
- "task_update": thay đổi trạng thái của một task trong danh sách OPEN TASKS —
  dùng ĐÚNG task_id từ danh sách đó; không khớp task nào → dùng new_task hoặc bỏ qua.
- "task_assignment": giao người cho một task đã có trong OPEN TASKS; chỉ dùng
  các assignee_user_ids được phép và được nhắc đến trong bằng chứng.
- self_assignment = true CHỈ khi chính tác giả của decided_by_message_id nói
  rõ họ sẽ tự làm việc; id của tác giả đó phải có trong assignee_user_ids.
- decided_by_message_id: id tin nhắn của NGƯỜI chốt việc/quyết định.
- evidence_message_ids: mọi id tin nhắn làm bằng chứng — chỉ dùng id có thật
  trong cửa sổ, tuyệt đối không bịa.
- confidence: mức chắc chắn thật của bạn; >= 0.9 chỉ khi chốt rành mạch không thể hiểu khác.
- Tin nhắn bắt đầu bằng "!decision" hoặc "!blocked" đã được hệ thống xử lý riêng — BỎ QUA.
- Không có gì đạt chuẩn → {"candidates": []}.
"""


def build_user_prompt(messages: list[Message], *, members: list[User],
                      open_tasks: list[Task], parties: list[Party],
                      context_messages: list[Message] | None = None,
                      allowed_assignee_ids: set[int] | None = None,
                      resolved_mentions_by_message: dict[int, set[int]] | None = None) -> str:
    member_lines = "\n".join(
        f"- user_id={u.id} {u.handle or u.name}: {u.name}"
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
    allowed_assignee_ids = allowed_assignee_ids or set()
    resolved_mentions_by_message = resolved_mentions_by_message or {}
    def render(message: Message, label: str) -> str:
        reply = f" reply_to={message.thread_ref}" if message.thread_ref is not None else ""
        mentions = sorted(resolved_mentions_by_message.get(message.id, set()))
        mention_ids = f" allowed_assignee_ids={mentions}" if mentions else ""
        return (f"[{message.id}] {label}{reply}{mention_ids} {message.ts:%Y-%m-%d %H:%M} "
                f"{message.author_identity}: {message.text}")

    context_lines = "\n".join(
        render(m, "CITE-ONLY — không được làm anchor")
        for m in (context_messages or []) if m.text.strip()
    ) or "- (không có)"
    message_lines = "\n".join(
        render(m, "PENDING — có thể làm anchor")
        for m in messages if m.text.strip()
    )
    return (
        f"THÀNH VIÊN:\n{member_lines}\n\n"
        f"OPEN TASKS (chỉ dùng các task_id này cho task_update):\n{task_lines}\n\n"
        f"ĐỐI TÁC / BÊN NGOÀI:\n{party_lines}\n\n"
        f"ID CÓ THỂ ĐƯỢC GIAO (chỉ khi được nhắc trong evidence): {sorted(allowed_assignee_ids)}\n\n"
        f"NGỮ CẢNH CŨ (chỉ được cite):\n{context_lines}\n\n"
        f"TIN NHẮN CHỜ XỬ LÝ (cửa sổ cần trích xuất):\n{message_lines}"
    )


def command_id(group_id: int, window_id: int, anchor_message_id: int,
               unit_key: str) -> uuid.UUID:
    """Deterministic per persisted window and candidate semantic unit.

    Epoch seconds are not a unique live-capture window identity. Materialization
    still provides cross-window replay dedup if an operator loses a cursor.
    """
    return uuid.uuid5(uuid.NAMESPACE_URL,
                      f"evermind-extract:{group_id}:{window_id}:{anchor_message_id}:{unit_key}")


def candidate_unit_key(candidate: ExtractedCandidate) -> str:
    """Materialization dedup key. Unlike the marker lane (one message = one
    task), one anchor message can legitimately decide SEVERAL new tasks — the
    description is part of the key so siblings don't dedup each other, while a
    re-extraction of the same window still does."""
    if candidate.kind == "task_update":
        return f"task:{candidate.task_id}|status:{candidate.status or 'done'}"
    if candidate.kind == "task_assignment":
        assignees = ",".join(str(user_id) for user_id in sorted(set(candidate.assignee_user_ids)))
        return f"task:{candidate.task_id}|assignment:{assignees}"
    return f"{candidate.kind}|{candidate.description}"


def candidate_to_command(
    candidate: ExtractedCandidate, *, index: int, group: ChatGroup,
    author: User, anchor: Message, window_id: int,
    from_epoch: int, to_epoch: int, messages_by_id: dict[int, Message],
) -> ProposeDecision | RecordTaskUpdate:
    cid = command_id(group.id, window_id, anchor.id, candidate_unit_key(candidate))
    persona = author.handle or anchor.author_identity
    if candidate.kind == "task_update":
        return RecordTaskUpdate(
            client_command_id=cid, persona=persona, created_from=CreatedFrom.LLM,
            confidence=candidate.confidence, ts=anchor.ts, window_id=window_id,
            source_message_id=anchor.id, task_id=candidate.task_id or 0,
            actor_user_id=author.id, update_kind="status",
            payload={"status": candidate.status or "done"},
        )
    target = f"task:{candidate.task_id}" if candidate.kind == "task_assignment" else "NEW_TASK"
    ops = ([] if candidate.kind == "task_assignment" else [OpSpec(target="NEW_TASK", facet="description", op="set",
                  value=candidate.description)]
    )
    ops.extend(
        OpSpec(target=target, facet="assignment", op="add", value=user_id)
        for user_id in candidate.assignee_user_ids
    )
    if candidate.status == "blocked" and candidate.kind == "new_task":
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
        scope=DecisionScope.TASK, scope_target=target,
        description=candidate.description, ops=ops, citations=citations,
        context_group_id=group.id,
    )

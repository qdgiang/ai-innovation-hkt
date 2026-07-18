"""Owner: A. Windows, markers, hydration, extraction, linkage, signals-emit."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.config import settings
from evermind.connectors.models import Message
from evermind.connectors.service import ConnectorsService
from evermind.contracts.commands import CitationSpec, OpSpec, ProposeDecision
from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionScope
from evermind.decisions.service import DecisionsService
from evermind.ingestion.extraction import (
    SYSTEM_PROMPT, ExtractedCandidate, ExtractionResult, build_user_prompt,
    candidate_to_command, candidate_unit_key,
)
from evermind.ingestion.identity import ADAPTERS, AuthorResolver
from evermind.ingestion.models import ExtractionWindow, IngestCursor, Materialization
from evermind.llm.client import LLMGateway, LLMUnavailable
from evermind.org.models import ChatGroup, Party
from evermind.org.service import OrgService
from evermind.tasks.consumer import TasksConsumer
from evermind.tasks.service import TasksService


_MARKER_RE = re.compile(r"^!(decision|blocked)\b\s*[—-]?\s*(.+)$", re.IGNORECASE)


def _aware(dt: datetime) -> datetime:
    """Columns are TIMESTAMPTZ (G54) but SQLite test runs hand back naive —
    normalize to aware-UTC before arithmetic."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

class IngestionService:
    def __init__(self, session: Session):
        self.session = session

    def run_pending_windows(self, *, gateway: LLMGateway | None = None) -> list[dict]:
        """One ING beat — the scheduler job and the manual
        `POST /ingestion/extract` both call exactly this.

        Sweeps LIVE-platform groups only (platforms registered in
        `identity.ADAPTERS`): replay/corpus groups are the seeder's story, and
        a cursor-less first beat over them would re-extract the whole corpus.
        A corpus group stays extractable via an explicit `run_window(group_id)`
        (the golden-set eval path)."""
        results: list[dict] = []
        live_groups = self.session.scalars(
            select(ChatGroup.id)
            .where(ChatGroup.platform.in_(tuple(ADAPTERS)))
            .order_by(ChatGroup.id))
        for group_id in live_groups:
            outcome = self.run_window(group_id, gateway=gateway)
            if outcome is not None:
                results.append(outcome)
        return results

    def run_window(self, group_id: int, *,
                   gateway: LLMGateway | None = None) -> dict | None:
        """ING-2 window + ING-3 hydrate + ING-4 extract + ING-5 link, one group.

        Window = messages after the group's cursor, capped at
        `EXTRACTION_BATCH_SIZE`, read via `connectors.service.read_pending`
        (interface #1). The cursor stores EPOCH SECONDS of the last processed
        message ts — not a message id, because live sources' synthetic ids are
        not time-ordered — and advances ONLY when the window's outputs persist:
        an `LLMUnavailable` window is marked failed and the same messages are
        retried next beat. Returns None when nothing is pending.
        """
        group = self.session.get(ChatGroup, group_id)
        if group is None:
            return None
        now = datetime.now(timezone.utc)
        cursor = self.session.get(IngestCursor, group_id)
        after = datetime.fromtimestamp(cursor.high_water_seq if cursor else 0,
                                       tz=timezone.utc)
        pending = ConnectorsService(self.session).read_pending(
            group_id, after=after, limit=settings.extraction_batch_size)
        if not pending:
            return None
        newest = _aware(pending[-1].ts)
        if now - newest < timedelta(seconds=settings.extraction_settle_sec):
            # chat is still flowing — never cut a conversation mid-thought
            return {"group_id": group_id, "status": "settling",
                    "pending": len(pending)}
        from_epoch = int(_aware(pending[0].ts).timestamp())
        to_epoch = int(newest.timestamp())
        prompt_messages = [m for m in pending
                           if m.text.strip() and not _MARKER_RE.match(m.text.strip())]
        if not prompt_messages:
            # media-only / marker-only window: nothing for the LLM, just advance
            self._advance_cursor(group_id, to_epoch)
            self.session.commit()
            return {"group_id": group_id, "status": "empty_window",
                    "messages": len(pending)}

        window = ExtractionWindow(group_id=group_id, source="chat",
                                  from_seq=from_epoch, to_seq=to_epoch,
                                  status="running", attempt=1, started_at=now)
        self.session.add(window)
        self.session.flush()

        org = OrgService(self.session)
        member_ids = org.members_of_team(group.team_id) if group.team_id else []
        members = [u for u in (org.get_user(uid) for uid in member_ids) if u]
        open_tasks = TasksService(self.session).list_tasks(
            project_id=group.project_id, statuses=("todo", "doing", "blocked"))
        parties = list(self.session.scalars(select(Party)))

        try:
            result, call = (gateway or LLMGateway()).call_json(
                system=SYSTEM_PROMPT,
                user=build_user_prompt(prompt_messages, members=members,
                                       open_tasks=open_tasks, parties=parties),
                schema=ExtractionResult,
            )
        except LLMUnavailable as exc:
            window.status = "failed"
            window.finished_at = datetime.now(timezone.utc)
            self.session.commit()  # cursor untouched — window retries next beat
            return {"group_id": group_id, "status": "llm_unavailable",
                    "window_id": window.id, "detail": str(exc)}

        window.tokens_in, window.tokens_out = call.tokens_in, call.tokens_out
        messages_by_id = {m.id: m for m in pending}
        service = DecisionsService(self.session, task_port=TasksService(self.session))
        outcomes = [
            self._materialize_candidate(
                candidate, index=index, group=group, window=window,
                from_epoch=from_epoch, to_epoch=to_epoch,
                messages_by_id=messages_by_id, service=service)
            for index, candidate in enumerate(result.candidates)
        ]
        self._advance_cursor(group_id, to_epoch)
        window.status = "done"
        window.finished_at = datetime.now(timezone.utc)
        TasksConsumer(self.session).poll_and_apply()
        self.session.commit()
        return {"group_id": group_id, "status": "done", "window_id": window.id,
                "messages": len(pending), "candidates": len(result.candidates),
                "outcomes": outcomes}

    def _materialize_candidate(
        self, candidate: ExtractedCandidate, *, index: int, group: ChatGroup,
        window: ExtractionWindow, from_epoch: int, to_epoch: int,
        messages_by_id: dict[int, Message], service: DecisionsService,
    ) -> dict:
        anchor = messages_by_id.get(candidate.decided_by_message_id)
        if anchor is None or any(mid not in messages_by_id
                                 for mid in candidate.evidence_message_ids):
            return {"index": index, "status": "hallucinated_message_ids"}
        if _MARKER_RE.match(anchor.text.strip()):
            return {"index": index, "status": "marker_lane_owns_it"}
        if candidate.kind == "task_update" and candidate.task_id is None:
            return {"index": index, "status": "missing_task_id"}
        unit_key = candidate_unit_key(candidate)
        existing = self.session.scalar(select(Materialization).where(
            Materialization.source_message_id == anchor.id,
            Materialization.unit_key == unit_key,
        ))
        if existing is not None:
            return {"index": index, "status": "already_materialized",
                    "decision_id": existing.decision_id}
        author = AuthorResolver(self.session).resolve(anchor, team_id=group.team_id)
        if author is None:
            return {"index": index, "status": "unresolved_author",
                    "reason": anchor.author_identity}
        command = candidate_to_command(
            candidate, index=index, group=group, author=author, anchor=anchor,
            window_id=window.id, from_epoch=from_epoch, to_epoch=to_epoch,
            messages_by_id=messages_by_id)
        outcome = service.handle(command, commit=False)
        # decisions come back with decision_id; the update lane answers with
        # status applied/pending_confirm (+task_id) and no id at all
        materialized = (outcome.get("decision_id") is not None
                        or outcome.get("update_id") is not None
                        or outcome.get("status") in ("applied", "pending_confirm"))
        if not materialized:
            return {"index": index, "status": "rejected_by_gateway",
                    "outcome": outcome}
        self.session.add(Materialization(
            source_message_id=anchor.id, command_index=index, kind="llm",
            unit_key=unit_key, decision_id=outcome.get("decision_id"),
            update_id=outcome.get("update_id")))
        return {"index": index, "status": outcome.get("status"),
                "decision_id": outcome.get("decision_id"),
                "task_id": outcome.get("task_id"),
                "confidence": candidate.confidence}

    def _advance_cursor(self, group_id: int, to_epoch: int) -> None:
        cursor = self.session.get(IngestCursor, group_id)
        if cursor is None:
            self.session.add(IngestCursor(group_id=group_id, high_water_seq=to_epoch))
        else:
            cursor.high_water_seq = max(cursor.high_water_seq, to_epoch)

    def apply_markers(self, message_id: int) -> list[dict]:
        """Materialize a supported marker exactly once through the command gate.

        Marker text is intentionally narrow: the marker itself supplies a
        task description, while richer linkage remains the later window lane.
        """
        message = self.session.get(Message, message_id)
        if message is None:
            raise LookupError(f"message {message_id} not found")
        match = _MARKER_RE.match(message.text.strip())
        if match is None:
            return []

        marker_kind, description = match.groups()
        existing = self.session.scalar(select(Materialization).where(
            Materialization.source_message_id == message.id,
            Materialization.command_index == 0,
            Materialization.kind == marker_kind.lower(),
            Materialization.unit_key == "NEW_TASK|description",
        ))
        if existing is not None:
            return [{"status": "already_materialized", "decision_id": existing.decision_id}]
        if message.group_id is None:
            return [{"status": "unrouted", "reason": "marker source has no chat group"}]

        group = self.session.get(ChatGroup, message.group_id)
        if group is None:
            return [{"status": "unresolved_author", "reason": message.author_identity}]
        # Platform-adapted resolution (ingestion/identity.py): [D5] identity key
        # for live platforms — with the G44 provisional lane — handle otherwise.
        user = AuthorResolver(self.session).resolve(message, team_id=group.team_id)
        if user is None:
            return [{"status": "unresolved_author", "reason": message.author_identity}]

        ops = [OpSpec(target="NEW_TASK", facet="description", op="set", value=description)]
        if marker_kind.lower() == "blocked":
            ops.append(OpSpec(target="NEW_TASK", facet="status", op="set", value="blocked"))
        command = ProposeDecision(
            client_command_id=uuid4(), persona=user.handle or message.author_identity,
            created_from=CreatedFrom.MARKER, confidence=1.0, ts=message.ts,
            source_message_id=message.id, decided_by_user_id=user.id,
            scope=DecisionScope.TASK, scope_target="NEW_TASK", description=description,
            ops=ops, context_group_id=group.id,
            citations=[CitationSpec(message_id=message.id, kind=CitationKind.EVIDENCE,
                                    rev_at_capture=message.current_rev)],
        )
        outcome = DecisionsService(
            self.session, task_port=TasksService(self.session)
        ).handle(command, commit=False)
        if outcome.get("decision_id") is None and outcome.get("update_id") is None:
            self.session.rollback()
            return [outcome]
        self.session.add(Materialization(
            source_message_id=message.id, command_index=0, kind=marker_kind.lower(),
            unit_key="NEW_TASK|description", decision_id=outcome.get("decision_id"), update_id=None,
        ))
        TasksConsumer(self.session).poll_and_apply()
        self.session.commit()
        return [outcome]

    def on_transcript_uploaded(self, upload_id: int) -> list[dict]:
        """Report an honest result until the non-marker transcript lane lands.

        Transcript messages carry no deterministic marker contract, so claiming
        they were extracted would be false. The upload remains durable and is
        explicitly surfaced as pending the window/LLM extractor.
        """
        return [{"status": "stored_pending_extraction", "upload_id": upload_id}]

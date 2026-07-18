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
from evermind.org.models import ChatGroup, Party, Team, UserTeam
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
                   gateway: LLMGateway | None = None,
                   allowed_assignee_ids: set[int] | None = None) -> dict | None:
        """ING-2 window + ING-3 hydrate + ING-4 extract + ING-5 link, one group.

        Window = messages after the group's cursor, capped at
        `EXTRACTION_BATCH_SIZE`, read via `connectors.service.read_pending`
        (interface #1). The cursor stores the capture-order tuple
        `(captured_at, message_id)` and advances ONLY when the window's outputs persist:
        an `LLMUnavailable` window is marked failed and the same messages are
        retried next beat. Returns None when nothing is pending.
        """
        group = self.session.get(ChatGroup, group_id)
        if group is None:
            return None
        now = datetime.now(timezone.utc)
        cursor = self.session.get(IngestCursor, group_id)
        after = (cursor.captured_at if cursor and cursor.captured_at else
                 datetime.fromtimestamp(cursor.high_water_seq if cursor else 0,
                                        tz=timezone.utc))
        pending = ConnectorsService(self.session).read_pending(
            group_id, after=after, after_id=(cursor.message_id or 0) if cursor else 0,
            limit=settings.extraction_batch_size)
        if not pending:
            return None
        def captured(message: Message) -> datetime:
            return _aware(getattr(message, "captured_at", message.ts))
        newest = captured(pending[-1])
        oldest = captured(pending[0])
        if (now - newest < timedelta(seconds=settings.extraction_settle_sec)
                and now - oldest < timedelta(seconds=settings.extraction_max_wait_sec)):
            # chat is still flowing — never cut a conversation mid-thought
            return {"group_id": group_id, "status": "settling",
                    "pending": len(pending)}
        from_epoch = int(_aware(pending[0].ts).timestamp())
        to_epoch = int(newest.timestamp())
        prompt_messages = [m for m in pending
                           if m.text.strip() and not _MARKER_RE.match(m.text.strip())]
        if not prompt_messages:
            # media-only / marker-only window: nothing for the LLM, just advance
            self._advance_cursor(group_id, to_epoch, pending[-1])
            self.session.commit()
            return {"group_id": group_id, "status": "empty_window",
                    "messages": len(pending)}

        window = ExtractionWindow(group_id=group_id, source="chat",
                                  from_seq=from_epoch, to_seq=to_epoch,
                                  status="running", attempt=1, started_at=now)
        self.session.add(window)
        self.session.flush()

        org = OrgService(self.session)
        member_ids = (org.members_of_team(group.team_id) if group.team_id else list(
            self.session.scalars(
                select(UserTeam.user_id).join(Team, Team.id == UserTeam.team_id)
                .where(Team.project_id == group.project_id).distinct()
            )
        ))
        members = [u for u in (org.get_user(uid) for uid in member_ids) if u]
        open_tasks = TasksService(self.session).list_tasks(
            project_id=group.project_id, statuses=("todo", "doing", "blocked"))
        parties = list(self.session.scalars(select(Party)))
        context_messages = ConnectorsService(self.session).hydrate_context(group_id, pending)
        messages_by_id = {message.id: message for message in [*context_messages, *pending]}
        pending_ids = {message.id for message in pending}
        resolved_mentions_by_message = self._resolved_mention_ids(
            group, messages_by_id.values(), {member.id for member in members})
        allowed_assignee_ids = allowed_assignee_ids or set().union(*resolved_mentions_by_message.values())

        try:
            result, call = (gateway or LLMGateway()).call_json(
                system=SYSTEM_PROMPT,
                user=build_user_prompt(prompt_messages, context_messages=context_messages,
                                       members=members, open_tasks=open_tasks, parties=parties,
                                       allowed_assignee_ids=allowed_assignee_ids,
                                       resolved_mentions_by_message=resolved_mentions_by_message),
                schema=ExtractionResult,
            )
        except LLMUnavailable as exc:
            window.status = "failed"
            window.finished_at = datetime.now(timezone.utc)
            self.session.commit()  # cursor untouched — window retries next beat
            return {"group_id": group_id, "status": "llm_unavailable",
                    "window_id": window.id, "detail": str(exc)}

        window.tokens_in, window.tokens_out = call.tokens_in, call.tokens_out
        service = DecisionsService(self.session, task_port=TasksService(self.session))
        seen_unit_keys: set[tuple[int, str]] = set()
        outcomes: list[dict] = []
        for index, candidate in enumerate(result.candidates):
            outcome = self._materialize_candidate(
                candidate, index=index, group=group, window=window,
                from_epoch=from_epoch, to_epoch=to_epoch, messages_by_id=messages_by_id,
                pending_ids=pending_ids, open_task_ids={task.id for task in open_tasks},
                allowed_assignee_ids=allowed_assignee_ids, member_user_ids=set(member_ids),
                seen_unit_keys=seen_unit_keys,
                resolved_mentions_by_message=resolved_mentions_by_message,
                service=service)
            outcomes.append(outcome)
        self._advance_cursor(group_id, to_epoch, pending[-1])
        errors = [outcome for outcome in outcomes if outcome["status"] not in (
            "effective", "proposed", "applied", "pending_confirm", "already_materialized")]
        window.error_count = len(errors)
        window.error_summary = {str(outcome["index"]): outcome["status"] for outcome in errors[:20]}
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
        messages_by_id: dict[int, Message], pending_ids: set[int], open_task_ids: set[int],
        allowed_assignee_ids: set[int], member_user_ids: set[int],
        seen_unit_keys: set[tuple[int, str]],
        resolved_mentions_by_message: dict[int, set[int]],
        service: DecisionsService,
    ) -> dict:
        anchor = messages_by_id.get(candidate.decided_by_message_id)
        if anchor is None or anchor.id not in pending_ids or any(mid not in messages_by_id
                                 for mid in candidate.evidence_message_ids):
            return {"index": index, "status": "hallucinated_message_ids"}
        if _MARKER_RE.match(anchor.text.strip()):
            return {"index": index, "status": "marker_lane_owns_it"}
        if candidate.kind in ("task_update", "task_assignment") and candidate.task_id is None:
            return {"index": index, "status": "missing_task_id"}
        if candidate.kind in ("task_update", "task_assignment") and candidate.task_id not in open_task_ids:
            return {"index": index, "status": "invalid_task_id"}
        author = AuthorResolver(self.session).resolve(anchor, team_id=group.team_id)
        if author is None:
            return {"index": index, "status": "unresolved_author",
                    "reason": anchor.author_identity}
        if candidate.self_assignment and author.id not in candidate.assignee_user_ids:
            return {"index": index, "status": "invalid_self_assignment"}
        permitted_assignee_ids = set(allowed_assignee_ids)
        if candidate.self_assignment and author.id in member_user_ids:
            permitted_assignee_ids.add(author.id)
        if candidate.assignee_user_ids and not set(candidate.assignee_user_ids) <= permitted_assignee_ids:
            return {"index": index, "status": "invalid_assignee_ids"}
        grounded_assignees = set().union(*(
            resolved_mentions_by_message.get(mid, set())
            for mid in candidate.evidence_message_ids
        ))
        if candidate.self_assignment:
            grounded_assignees.add(author.id)
        if candidate.assignee_user_ids and not set(candidate.assignee_user_ids) <= grounded_assignees:
            return {"index": index, "status": "ungrounded_assignee_ids"}
        unit_key = candidate_unit_key(candidate)
        candidate_key = (anchor.id, unit_key)
        if candidate_key in seen_unit_keys:
            return {"index": index, "status": "duplicate_in_window"}
        seen_unit_keys.add(candidate_key)
        existing = self.session.scalar(select(Materialization).where(
            Materialization.source_message_id == anchor.id,
            Materialization.unit_key == unit_key,
        ))
        if existing is not None:
            return {"index": index, "status": "already_materialized",
                    "decision_id": existing.decision_id}
        command = candidate_to_command(
            candidate, index=index, group=group, author=author, anchor=anchor,
            window_id=window.id, from_epoch=from_epoch, to_epoch=to_epoch,
            messages_by_id=messages_by_id)
        try:
            with self.session.begin_nested():
                outcome = service.handle(command, commit=False, rollback_on_error=False)
                # Materialization participates in the same savepoint as gateway writes.
                materialized = (outcome.get("decision_id") is not None
                                or outcome.get("update_id") is not None
                                or outcome.get("status") in ("applied", "pending_confirm"))
                if materialized:
                    self.session.add(Materialization(
                        source_message_id=anchor.id, command_index=index, kind="llm",
                        unit_key=unit_key, decision_id=outcome.get("decision_id"),
                        update_id=outcome.get("update_id")))
        except Exception:
            return {"index": index, "status": "candidate_crashed"}
        # decisions come back with decision_id; the update lane answers with
        # status applied/pending_confirm (+task_id) and no id at all
        if not materialized:
            return {"index": index, "status": "rejected_by_gateway",
                    "outcome": outcome}
        return {"index": index, "status": outcome.get("status"),
                "decision_id": outcome.get("decision_id"),
                "task_id": outcome.get("task_id"),
                "confidence": candidate.confidence}

    def _advance_cursor(self, group_id: int, to_epoch: int, message: Message | None = None) -> None:
        cursor = self.session.get(IngestCursor, group_id)
        if cursor is None:
            self.session.add(IngestCursor(
                group_id=group_id, high_water_seq=to_epoch,
                captured_at=getattr(message, "captured_at", message.ts) if message else None,
                message_id=message.id if message else None))
        else:
            cursor.high_water_seq = max(cursor.high_water_seq, to_epoch)
            if message is not None:
                cursor.captured_at = getattr(message, "captured_at", message.ts)
                cursor.message_id = message.id

    def _resolved_mention_ids(self, group: ChatGroup, messages, member_ids: set[int]) -> dict[int, set[int]]:
        """Resolve only stable Telegram IDs or learned scoped aliases; no display-name match."""
        resolved: dict[int, set[int]] = {}
        org = OrgService(self.session)
        adapter = ADAPTERS.get(group.platform)
        if adapter is None:
            return resolved
        for message in messages:
            users: set[int] = set()
            for mention in message.mentions or []:
                user = None
                platform_id = mention.get("platform_user_id")
                if platform_id:
                    user = org.resolve_identity(adapter.platform, adapter.connector_scope, str(platform_id))
                elif mention.get("username"):
                    user = org.resolve_username_alias(
                        adapter.platform, adapter.connector_scope, mention["username"])
                if user is not None and user.id in member_ids:
                    users.add(user.id)
            if users:
                resolved[message.id] = users
        return resolved

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

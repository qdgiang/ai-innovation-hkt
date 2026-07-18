"""Routes projection-owned commands into transactional domain events."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.commands import (
    AppendCorroboration,
    RecordSignal,
    RecordTaskUpdate,
    RegisterReactionAct,
)
from evermind.contracts.enums import DecisionStatus, TaskStatus
from evermind.decisions.authority import AuthorityResolver
from evermind.decisions.ordering import HandleContext
from evermind.decisions.persistence import append_event, serialize_targets
from evermind.decisions.models import Decision, DecisionCitation
from evermind.decisions.task_state import TaskStatePort, TaskStateView


class EventCommandRouter:
    def __init__(
        self,
        session: Session,
        *,
        authority: AuthorityResolver,
        task_state: TaskStatePort,
    ):
        self.session = session
        self.authority = authority
        self.task_state = task_state

    def route_task_update(
        self,
        command: RecordTaskUpdate,
        context: HandleContext,
    ) -> dict:
        task, redirected_from = self._resolve_task(command.task_id)
        if task is None:
            return {"ok": False, "status": "not_found", "http_status": 404}
        serialize_targets(self.session, {f"task:{task.id}"})
        base: dict = {"task_id": task.id, "version": task.current_version}
        if redirected_from is not None:
            base["redirected_from"] = redirected_from
        if self.authority.org.rank_of(command.actor_user_id) == 0:
            return {
                "ok": False,
                "status": "forbidden",
                "http_status": 403,
                "applied": False,
                "reason": "actor_has_no_active_authority",
                **base,
            }
        if task.status is TaskStatus.CANCELED and command.update_kind != "note":
            return {
                "ok": True,
                "status": "terminal_locked",
                "applied": False,
                "reason": "terminal:canceled",
                **base,
            }
        if task.is_pic(command.actor_user_id):
            lane = "pic"
        elif self.authority.can_decide(
            command.actor_user_id,
            f"v1|task:{task.id}|status",
        ):
            lane = "authority"
        else:
            return {
                "ok": True,
                "status": "confirmation_required",
                "applied": False,
                "required_pic_ids": sorted(task.pic_user_ids),
                **base,
            }
        append_event(
            self.session,
            context=context,
            kind="task_update_recorded",
            aggregate="task_update",
            aggregate_id=task.id,
            payload={
                "task_id": task.id,
                "actor_user_id": command.actor_user_id,
                "update_kind": command.update_kind,
                "payload": command.payload,
                "created_from": command.created_from.value,
                "confidence": command.confidence,
                "source_message_id": command.source_message_id,
                "lane": lane,
                **({"redirected_from": redirected_from} if redirected_from is not None else {}),
            },
            command_id=str(command.client_command_id),
        )
        return {
            "ok": True,
            "status": "applied",
            "applied": True,
            "lane": lane,
            **base,
        }

    def route_signal(self, command: RecordSignal, context: HandleContext) -> dict:
        if command.source_message_id is None:
            raise ValueError("signal requires source_message_id")
        append_event(
            self.session,
            context=context,
            kind="signal_recorded",
            aggregate="signal",
            aggregate_id=command.project_id,
            payload={
                "signal_kind": command.signal_kind,
                "project_id": command.project_id,
                "task_id": command.task_id,
                "party_id": command.party_id,
                "normalized_topic": command.normalized_topic,
                "excerpt": command.excerpt,
                "source_message_id": command.source_message_id,
                "window_id": command.window_id,
                "confidence": command.confidence,
                "created_from": command.created_from.value,
            },
            command_id=str(command.client_command_id),
        )
        return {
            "ok": True,
            "status": "recorded",
            "project_id": command.project_id,
        }

    def append_corroboration(
        self,
        command: AppendCorroboration,
        context: HandleContext,
    ) -> dict:
        decision = self.session.get(Decision, command.decision_id)
        if decision is None:
            return {"ok": False, "status": "not_found", "http_status": 404}
        existing = self.session.scalar(
            select(DecisionCitation).where(
                DecisionCitation.decision_id == command.decision_id,
                DecisionCitation.message_id == command.citation.message_id,
            )
        )
        appended = existing is None
        if appended:
            self.session.add(
                DecisionCitation(
                    decision_id=command.decision_id,
                    message_id=command.citation.message_id,
                    kind=command.citation.kind,
                    rev_at_capture=command.citation.rev_at_capture,
                    rev_at_act=command.citation.rev_at_act,
                )
            )
        append_event(
            self.session,
            context=context,
            kind="corroboration_appended",
            aggregate="decision",
            aggregate_id=command.decision_id,
            payload={
                "decision_id": command.decision_id,
                "message_id": command.citation.message_id,
                "appended": appended,
            },
            command_id=str(command.client_command_id),
        )
        return {
            "ok": True,
            "status": "corroborated",
            "decision_id": command.decision_id,
            "appended": appended,
        }

    def route_reaction(
        self,
        command: RegisterReactionAct,
        context: HandleContext,
    ) -> dict:
        tracked = self.session.scalar(
            select(DecisionCitation.id)
            .join(Decision, Decision.id == DecisionCitation.decision_id)
            .where(
                DecisionCitation.message_id == command.message_id,
                Decision.status == DecisionStatus.PROPOSED,
            )
            .limit(1)
        )
        if tracked is None:
            raise ValueError("reaction message is not tracked")
        append_event(
            self.session,
            context=context,
            kind="reaction_act_registered",
            aggregate="reaction_act",
            aggregate_id=command.message_id,
            payload={
                "message_id": command.message_id,
                "user_id": command.user_id,
                "emoji": command.emoji,
                "removed": command.removed,
            },
            command_id=str(command.client_command_id),
        )
        return {
            "ok": True,
            "status": "recorded",
            "message_id": command.message_id,
        }

    def _resolve_task(self, task_id: int) -> tuple[TaskStateView | None, int | None]:
        task = self.task_state.get_task(task_id)
        if task is None or task.status is not TaskStatus.MERGED:
            return task, None
        redirected_from = task.id
        seen = {task.id}
        while task.status is TaskStatus.MERGED:
            survivor_id = task.merged_survivor
            if survivor_id is None or survivor_id in seen:
                return None, redirected_from
            seen.add(survivor_id)
            task = self.task_state.get_task(survivor_id)
            if task is None:
                return None, redirected_from
        return task, redirected_from

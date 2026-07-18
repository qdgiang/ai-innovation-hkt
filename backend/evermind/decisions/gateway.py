"""Transactional command dispatch and processed-command idempotency."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.commands import (
    AppendCorroboration,
    ApproveProposal,
    Command,
    OpSpec,
    ProposeDecision,
    RecordSignal,
    RecordTaskUpdate,
    RegisterReactionAct,
    RejectProposal,
)
from evermind.contracts.enums import CreatedFrom, TaskStatus
from evermind.decisions.authority import AuthorityResolver
from evermind.decisions.decision_writer import DecisionWriter
from evermind.decisions.event_routes import EventCommandRouter
from evermind.decisions.facets import FacetRegistry, version_for_bindings
from evermind.decisions.models import Decision, ProcessedCommand
from evermind.decisions.ordering import HandleContext
from evermind.decisions.persistence import current_bindings_for_units, serialize_targets
from evermind.decisions.task_state import TaskStateView
from evermind.org.service import OrgService


class CommandGateway:
    def __init__(
        self,
        session: Session,
        *,
        org: OrgService,
        authority: AuthorityResolver,
        registry: FacetRegistry,
    ):
        self.session = session
        self.org = org
        self.registry = registry
        self.task_state = authority.task_state
        self.writer = DecisionWriter(
            session,
            org=org,
            authority=authority,
            registry=registry,
        )
        self.event_router = EventCommandRouter(
            session,
            authority=authority,
            task_state=authority.task_state,
        )

    def handle(self, command: Command, context: HandleContext | None = None) -> dict:
        command_id = str(command.client_command_id)
        context = context or HandleContext.now(command_id)
        transaction = (
            self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        )
        try:
            with transaction:
                return self._handle_in_transaction(command, context)
        except ValueError as exc:
            return {
                "ok": False,
                "status": "invalid",
                "http_status": 422,
                "error": str(exc),
            }

    def _handle_in_transaction(self, command: Command, context: HandleContext) -> dict:
        command_id = str(command.client_command_id)
        # A command-id lock closes the race between the receipt lookup and insert.
        # PostgreSQL advisory transaction locks are re-entrant for same-session retries.
        serialize_targets(self.session, {f"command:{command_id}"})
        existing = self.session.get(ProcessedCommand, command_id)
        if existing is not None:
            if existing.persona != command.persona:
                return {
                    "ok": False,
                    "status": "forbidden",
                    "http_status": 403,
                    "error": "client_command_id belongs to another persona",
                }
            return existing.outcome
        actor_user_id = (
            command.decided_by_user_id
            if isinstance(command, ProposeDecision)
            else command.approved_by_user_id
            if isinstance(command, ApproveProposal)
            else command.rejected_by_user_id
            if isinstance(command, RejectProposal)
            else command.actor_user_id
            if isinstance(command, RecordTaskUpdate)
            else command.user_id
            if isinstance(command, RegisterReactionAct)
            else None
        )
        if actor_user_id is None:
            persona_user = self.org.user_for_persona(command.persona)
            actor_user_id = persona_user.id if persona_user is not None else None
        if actor_user_id is None:
            return {"ok": False, "status": "forbidden", "http_status": 403}
        actor = self.org.get_user(actor_user_id)
        if actor is None or command.persona not in {str(actor.id), actor.handle}:
            return {"ok": False, "status": "forbidden", "http_status": 403}
        version_conflict = self._version_conflict(command, context)
        if version_conflict is not None:
            outcome = version_conflict
        elif isinstance(command, ProposeDecision):
            outcome = self.writer.propose(command, context)
        elif isinstance(command, ApproveProposal):
            outcome = self.writer.approve(command, context)
        elif isinstance(command, RecordTaskUpdate):
            outcome = self.event_router.route_task_update(command, context)
        elif isinstance(command, RejectProposal):
            outcome = self.writer.reject(command, context)
        elif isinstance(command, RecordSignal):
            outcome = self.event_router.route_signal(command, context)
        elif isinstance(command, AppendCorroboration):
            outcome = self.event_router.append_corroboration(command, context)
        elif isinstance(command, RegisterReactionAct):
            outcome = self.event_router.route_reaction(command, context)
        else:
            raise ValueError(f"unsupported command: {command.kind}")
        self.session.add(
            ProcessedCommand(
                client_command_id=command_id,
                persona=command.persona,
                received_at=context.recorded_at,
                outcome=outcome,
            )
        )
        self.session.flush()
        return outcome

    def _version_conflict(
        self,
        command: Command,
        context: HandleContext,
    ) -> dict | None:
        version_state = self._version_state(command, context)
        if version_state is None:
            return None
        version, diff = version_state
        if command.expected_version is None:
            if not self._dashboard_write_requires_version(command, context, diff):
                return None
            return {
                "ok": False,
                "status": "expected_version_required",
                "http_status": 409,
                "current_version": version,
                "diff": diff,
            }
        if command.expected_version == version:
            return None
        return {
            "ok": False,
            "status": "version_conflict",
            "http_status": 409,
            "expected_version": command.expected_version,
            "current_version": version,
            "diff": diff,
        }

    def _dashboard_write_requires_version(
        self,
        command: Command,
        context: HandleContext,
        bindings: dict,
    ) -> bool:
        if command.created_from is not CreatedFrom.DASHBOARD:
            return False
        if isinstance(command, RecordTaskUpdate):
            return command.update_kind == "status"
        if isinstance(command, (ApproveProposal, RejectProposal)):
            return True
        if not isinstance(command, ProposeDecision) or command.effect_window is not None:
            return False
        units = self.registry.derive_units(
            command.ops,
            stable_event_id=context.stable_event_id,
        )
        occupied = [unit for unit in units if unit.occupies]
        if not occupied or not bindings:
            return False
        standing = {
            decision.id: decision
            for decision in self.session.scalars(
                select(Decision).where(Decision.id.in_(set(bindings.values())))
            )
        }
        for unit in occupied:
            decision_id = bindings.get(unit.unit_key)
            if decision_id is None:
                # A wildcard set can conflict with existing slot-specific units.
                return True
            decision = standing.get(decision_id)
            if decision is None:
                return True
            standing_units = self.registry.derive_units(
                [OpSpec.model_validate(op) for op in decision.ops],
                stable_event_id=decision.stable_event_id or str(decision.id),
            )
            standing_values = {
                candidate.unit_key: (candidate.op, candidate.canonical_value)
                for candidate in standing_units
                if candidate.occupies
            }
            if standing_values.get(unit.unit_key) != (unit.op, unit.canonical_value):
                return True
        return False

    def _version_state(
        self,
        command: Command,
        context: HandleContext,
    ) -> tuple[str, dict] | None:
        if isinstance(command, ProposeDecision):
            units = self.registry.derive_units(
                command.ops,
                stable_event_id=context.stable_event_id,
            )
        elif isinstance(command, (ApproveProposal, RejectProposal)):
            decision = self.session.get(Decision, command.decision_id)
            if decision is None:
                return None
            units = self.registry.derive_units(
                [OpSpec.model_validate(op) for op in decision.ops],
                stable_event_id=decision.stable_event_id or str(decision.id),
            )
            # The body is append-only, so it is safe to derive locks from this
            # snapshot. Lifecycle fields must be reloaded only after waiting.
            serialize_targets(self.session, {unit.target for unit in units})
            self.session.refresh(decision)
        elif isinstance(command, RecordTaskUpdate):
            task = self._locked_task_target(command.task_id)
            if task is None:
                return None
            return task.current_version, {f"task:{task.id}": task.current_version}
        else:
            return None
        if not isinstance(command, (ApproveProposal, RejectProposal)):
            serialize_targets(self.session, {unit.target for unit in units})
        bindings = current_bindings_for_units(self.session, units)
        return version_for_bindings(bindings), bindings

    def _locked_task_target(self, task_id: int) -> TaskStateView | None:
        seen: set[int] = set()
        current_id = task_id
        while current_id not in seen:
            seen.add(current_id)
            serialize_targets(self.session, {f"task:{current_id}"})
            task = self.task_state.get_task(current_id)
            if task is None or task.status is not TaskStatus.MERGED:
                return task
            if task.merged_survivor is None:
                return None
            current_id = task.merged_survivor
        return None

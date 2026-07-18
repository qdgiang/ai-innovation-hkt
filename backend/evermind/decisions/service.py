"""Owner: A. THE UNIVERSAL COMMAND GATEWAY (architecture.md §The write pipeline).

Every `contracts.commands.Command` — including `RecordTaskUpdate`/`RecordSignal`
owned by B's modules — enters through `DecisionsService.handle`. This is the
ONLY place that may declare something `effective`, append `domain_events`, or
enforce `processed_commands` idempotency. `tasks`/`signals` never process raw
commands; they only project events (their `consumer.py`).

One transaction per command (D3): state rows + status flips + sweep +
`domain_events` append + `processed_commands` record commit together, or none
of it does.

Implements P1 Lane A: DEC-1 lifecycle · DEC-2 facet units (via `facets`) ·
DEC-3 effective-write transaction (flip + sweep + same-value guard G66 +
`effective_units`) · DEC-4 authority (via `authority`; at-act snapshots
[EVM-005]) · DEC-6 rejection/challenge/resurrection · DEC-7 hygiene (G49 merge,
#17b withdrawal, bulk acts) · DEC-8 effect-windows (+ overlap hold [EVM-004]) ·
DEC-9 multi-op atomicity [EVM-003] · ING-7 ordering (born-already-superseded
G31, tiebreak [EVM-012]) · [EVM-021] idempotency + expected-version.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.config import settings
from evermind.contracts.commands import (
    AppendCorroboration,
    ApproveProposal,
    BulkProposalAction,
    CitationSpec,
    Command,
    CommandEnvelope,
    OpSpec,
    ProposeDecision,
    RecordSignal,
    RecordTaskUpdate,
    RegisterReactionAct,
    RejectProposal,
)
from evermind.contracts.enums import (
    ApprovalVia,
    CitationKind,
    CreatedFrom,
    DecisionScope,
    DecisionStatus,
    RejectedReason,
    TaskStatus,
)
from evermind.contracts.ports import TaskReadPort
from evermind.db.eventlog import DomainEvent
from evermind.decisions.authority import AuthorityDecision, AuthorityService
from evermind.decisions.facets import UnitPlan, derive_unit_plan
from evermind.decisions.models import (
    Decision,
    DecisionCitation,
    DecisionTask,
    DecisionUnit,
    EffectiveUnit,
    IdAllocation,
    ProcessedCommand,
)
from evermind.org.service import OrgService

EXPECTED_VACANT = "vacant"  # expected_version sentinel: "I expect no standing decision"


def _utcnow() -> datetime:
    # timezone-AWARE: every timestamp column is TIMESTAMPTZ (db/base.py, G54);
    # Postgres returns aware datetimes, so naive locals would TypeError on
    # comparison the moment a row round-trips.
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize command-supplied timestamps to AWARE UTC (G54): naive inputs
    are taken as UTC, aware ones converted."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class DecisionsService:
    def __init__(
        self,
        session: Session,
        org: OrgService | None = None,
        task_port: TaskReadPort | None = None,
        tau: float | None = None,
    ):
        self.session = session
        self.org = org or OrgService(session)
        self.task_port = task_port
        self.authority = AuthorityService(self.org, task_port)
        self.tau = settings.confidence_tau if tau is None else tau

    # ══════════════════════════════════════════════════════════ entrypoint

    def handle(self, command: Command, *, commit: bool = True) -> dict:
        """The one write path (D3). Returns the command outcome — also the shape
        stored in `processed_commands.outcome` so retries replay it [EVM-021]."""
        command_id = str(command.client_command_id)
        recorded = self.session.get(ProcessedCommand, command_id)
        if recorded is not None:
            return {**recorded.outcome, "duplicate": True}
        try:
            outcome = self._dispatch(command)
            self.session.add(ProcessedCommand(
                client_command_id=command_id,
                persona=command.persona,
                received_at=_utcnow(),
                outcome=outcome,
            ))
            if commit:
                self.session.commit()
            else:
                self.session.flush()
        except Exception:
            self.session.rollback()
            raise
        return outcome

    def _dispatch(self, command: Command) -> dict:
        if isinstance(command, ProposeDecision):
            return self._propose(command)
        if isinstance(command, ApproveProposal):
            return self._approve(command)
        if isinstance(command, RejectProposal):
            return self._reject(command)
        if isinstance(command, BulkProposalAction):
            return self._bulk(command)
        if isinstance(command, RecordTaskUpdate):
            return self._record_task_update(command)
        if isinstance(command, RecordSignal):
            return self._record_signal(command)
        if isinstance(command, AppendCorroboration):
            return self._append_corroboration(command)
        if isinstance(command, RegisterReactionAct):
            # DEC-5 chat acts open in P3 (plan.md agreement 5 — don't build ahead)
            return {"status": "deferred", "reason": "reaction acts land in P3 (DEC-5)"}
        raise ValueError(f"unknown command: {type(command).__name__}")

    # ═══════════════════════════════════════════════════════ event helper

    def _emit(self, kind: str, aggregate: str, aggregate_id: int, payload: dict,
              ts: datetime | None, command: CommandEnvelope) -> None:
        self.session.add(DomainEvent(
            ts=ts or _utcnow(), kind=kind, aggregate=aggregate,
            aggregate_id=aggregate_id, payload=payload,
            caused_by_command=str(command.client_command_id),
        ))

    def _decision_payload(self, decision: Decision, **extra: Any) -> dict:
        payload = {
            "decision_id": decision.id,
            "ts": _iso(decision.ts),
            "recorded_at": _iso(decision.recorded_at),
            "decided_by_user_id": decision.decided_by_user_id,
            "decided_by_role_at_time": decision.decided_by_role_at_time,
            "scope": decision.scope.value,
            "scope_target": decision.scope_target,
            "description": decision.description,
            "ops": decision.ops,
            "status": decision.status.value,
            "effect_window": (
                {"from": _iso(decision.effect_window_from),
                 "until": _iso(decision.effect_window_until)}
                if decision.effect_window_from else None
            ),
            "created_from": decision.created_from.value,
            "confidence": decision.confidence,
            "window_id": decision.window_id,
        }
        payload.update(extra)
        return payload

    # ══════════════════════════════════════════════ shared decision infra

    def _sort_key(self, ts: datetime, recorded_at: datetime,
                  stable_event_id: str | None) -> tuple:
        """[EVM-012] fold/supersession order: (ts, recorded_at, stable_event_id)."""
        return (ts, recorded_at, stable_event_id or "")

    def _decision_key(self, decision: Decision) -> tuple:
        return self._sort_key(decision.ts, decision.recorded_at, decision.stable_event_id)

    def _standing_occupants(self, units: list[str], prefixes: list[str]
                            ) -> dict[str, Decision]:
        """unit_key -> the effective decision occupying it (incl. prefix hits
        for slot-facet `set` displacement)."""
        occupants: dict[str, Decision] = {}
        rows = list(self.session.scalars(select(EffectiveUnit)))
        for row in rows:
            hit = row.unit_key in units or any(
                row.unit_key == p or row.unit_key.startswith(p + "|") for p in prefixes
            )
            if hit:
                decision = self.session.get(Decision, row.decision_id)
                if decision is not None:
                    occupants[row.unit_key] = decision
        return occupants

    def _units_of(self, decision_id: int) -> list[str]:
        return list(self.session.scalars(
            select(DecisionUnit.unit_key).where(DecisionUnit.decision_id == decision_id)
        ))

    def _allocate_task_id(self) -> int:
        row = self.session.get(IdAllocation, "task", with_for_update=True)
        if row is None:
            row = IdAllocation(name="task", next_id=1)
            self.session.add(row)
            self.session.flush()
        allocated = row.next_id
        row.next_id = allocated + 1
        return allocated

    def _insert_decision(self, cmd: ProposeDecision, *, ts: datetime,
                         recorded_at: datetime, status: DecisionStatus,
                         plan: UnitPlan, rank_snapshot: int,
                         approval_via: ApprovalVia | None = None,
                         approved_by: int | None = None) -> Decision:
        stable = (f"msg:{cmd.source_message_id}" if cmd.source_message_id is not None
                  else f"cmd:{cmd.client_command_id}")
        window = cmd.effect_window
        decision = Decision(
            ts=ts, recorded_at=recorded_at,
            decided_by_user_id=cmd.decided_by_user_id,
            decided_by_role_at_time=rank_snapshot,
            scope=cmd.scope, scope_target=cmd.scope_target,
            description=cmd.description, context=cmd.context, note=cmd.note,
            ops=[op.model_dump() for op in cmd.ops],
            effect_window_from=_as_utc(window[0]) if window else None,
            effect_window_until=_as_utc(window[1]) if window else None,
            status=status,
            approved_by_user_id=approved_by,
            approval_via=approval_via,
            approved_by_role_at_act=(self.org.rank_of(approved_by)
                                     if approved_by is not None else None),
            created_from=cmd.created_from,
            confidence=(1.0 if cmd.created_from in (CreatedFrom.MARKER, CreatedFrom.DASHBOARD)
                        else cmd.confidence),
            window_id=cmd.window_id,
            stable_event_id=stable,
        )
        self.session.add(decision)
        self.session.flush()
        for citation in cmd.citations:
            self.session.add(DecisionCitation(
                decision_id=decision.id, message_id=citation.message_id,
                kind=citation.kind, rev_at_capture=citation.rev_at_capture,
                rev_at_act=citation.rev_at_act,
            ))
        if cmd.delegation_message_id is not None:
            self.session.add(DecisionCitation(
                decision_id=decision.id, message_id=cmd.delegation_message_id,
                kind=CitationKind.EVIDENCE, rev_at_capture=1,
            ))
        for task_id in plan.task_ids:
            self.session.add(DecisionTask(decision_id=decision.id, task_id=task_id))
        for unit in plan.occupied_units:
            self.session.add(DecisionUnit(decision_id=decision.id, unit_key=unit))
        self.session.flush()
        return decision

    def _effective_write(self, winner: Decision, plan: UnitPlan,
                         command: CommandEnvelope) -> dict:
        """DEC-3: flip same-unit predecessors + sweep same-unit proposeds +
        occupy `effective_units` — all in the caller's transaction. The caller
        has already run the same-value guard, authority, rank/peer gates,
        ordering, and window checks."""
        occupants = self._standing_occupants(plan.occupied_units, plan.displaced_prefixes)
        superseded_ids: list[int] = []
        for decision in {d.id: d for d in occupants.values()}.values():
            if decision.id == winner.id:
                continue
            decision.status = DecisionStatus.SUPERSEDED
            decision.superseded_by_decision_id = winner.id
            superseded_ids.append(decision.id)
            self._emit("decision_superseded", "decision", decision.id,
                       {"decision_id": decision.id, "superseded_by": winner.id},
                       winner.ts, command)
        if len(superseded_ids) == 1:
            winner.supersedes_decision_id = superseded_ids[0]

        # vacate displaced units, then occupy the winner's. A superseded
        # decision's status is atomic, so ALL its units vacate — a multi-op
        # decision losing one unit releases the rest too ([EVM-003] downstream;
        # history keeps the values via decision_units + the event log).
        claimed_units = set(plan.occupied_units)  # units the winner takes over
        superseded_set = set(superseded_ids)
        for row in list(self.session.scalars(select(EffectiveUnit))):
            prefix_hit = any(row.unit_key == p or row.unit_key.startswith(p + "|")
                             for p in plan.displaced_prefixes)
            if prefix_hit:
                claimed_units.add(row.unit_key)
            if row.unit_key in claimed_units or row.decision_id in superseded_set:
                self.session.delete(row)
        self.session.flush()
        for unit in plan.occupied_units:
            self.session.add(EffectiveUnit(unit_key=unit, decision_id=winner.id))

        # sweep same-unit proposeds -> rejected(overruled), authors notified
        # (G11/G12). Windowed pendings are NOT competing for the unit (G42) —
        # they wait for their own human act (#18).
        swept_ids: list[int] = []
        pending_rows = self.session.execute(
            select(Decision, DecisionUnit.unit_key)
            .join(DecisionUnit, DecisionUnit.decision_id == Decision.id)
            .where(Decision.status == DecisionStatus.PROPOSED,
                   Decision.effect_window_from.is_(None),
                   Decision.id != winner.id)
        ).all()
        for decision, unit_key in pending_rows:
            if unit_key in claimed_units and decision.id not in swept_ids:
                decision.status = DecisionStatus.REJECTED
                decision.rejected_reason = RejectedReason.OVERRULED
                decision.superseded_by_decision_id = winner.id
                swept_ids.append(decision.id)
                self._emit("decision_rejected", "decision", decision.id,
                           {"decision_id": decision.id, "rejected_reason": "overruled",
                            "superseded_by": winner.id,
                            "notify_user_id": decision.decided_by_user_id},
                           winner.ts, command)
        self.session.flush()
        return {"superseded": superseded_ids, "swept_overruled": swept_ids}

    # ═══════════════════════════════════════════════════════ propose (DEC-1/3/8/9, ING-7)

    def _propose(self, cmd: ProposeDecision) -> dict:
        if not cmd.ops:
            return {"status": "invalid", "error": "a decision needs at least one op"}
        # Invariant #1: chat-originated decisions carry >=1 evidence citation
        if cmd.created_from in (CreatedFrom.MARKER, CreatedFrom.LLM) and not any(
            c.kind == CitationKind.EVIDENCE for c in cmd.citations
        ):
            return {"status": "invalid",
                    "error": "chat-originated decisions need >=1 evidence citation"}

        recorded_at = _utcnow()
        ts = _as_utc(cmd.ts) or recorded_at
        if cmd.created_from is CreatedFrom.LLM and ts > recorded_at + timedelta(days=1):
            # A model cannot assert an event substantially after it was recorded.
            # Directly cited marker events may be replayed from a recorded demo whose
            # logical event clock is later than this machine's wall clock.
            self._emit("triage_raised", "command", 0,
                       {"reason": "impossible_chronology", "ts": _iso(ts),
                        "recorded_at": _iso(recorded_at),
                        "client_command_id": str(cmd.client_command_id)},
                       recorded_at, cmd)
            return {"status": "triage", "reason": "impossible_chronology"}

        plan = derive_unit_plan(cmd.ops)
        # G3: authority must see the PRE-rewrite targets — a NEW_TASK op
        # authorizes via the context group's team, never via the freshly
        # allocated task id (which is not in the projection yet → apex-only).
        auth_targets = sorted({op.target for op in cmd.ops} or {cmd.scope_target})
        new_task_id: int | None = None
        if plan.has_new_task:
            new_task_id = self._allocate_task_id()
            rewritten = []
            for op in cmd.ops:
                target = f"task:{new_task_id}" if op.target == "NEW_TASK" else op.target
                rewritten.append(OpSpec(target=target, facet=op.facet, op=op.op,
                                        value=op.value))
            cmd = cmd.model_copy(update={
                "ops": rewritten,
                "scope_target": (f"task:{new_task_id}"
                                 if cmd.scope_target == "NEW_TASK" else cmd.scope_target),
            })
            plan = derive_unit_plan(cmd.ops)

        occupants = self._standing_occupants(plan.occupied_units, plan.displaced_prefixes)

        # [EVM-021] expected-version: mismatch => 409-shaped outcome + diff, never
        # a silent overwrite
        if cmd.expected_version is not None:
            conflict = self._version_conflict(cmd.expected_version, plan, occupants)
            if conflict is not None:
                return conflict

        # G66 same-value guard: candidate equal (op+value) to the standing unit
        # becomes a corroborating citation — attribution and ts never move
        if plan.occupied_units and all(
            unit in occupants
            and self._occupant_value(occupants[unit], unit) == plan.unit_values[unit]
            for unit in plan.occupied_units
        ):
            corroborated: list[int] = []
            for decision in {d.id: d for d in occupants.values()}.values():
                for citation in cmd.citations:
                    self._add_citation_once(decision.id, citation,
                                            CitationKind.CORROBORATION)
                corroborated.append(decision.id)
                self._emit("corroboration_appended", "decision", decision.id,
                           {"decision_id": decision.id,
                            "message_ids": [c.message_id for c in cmd.citations],
                            "restated_by": cmd.decided_by_user_id, "at": _iso(ts)},
                           ts, cmd)
            return {"status": "corroborated", "decision_ids": corroborated}

        # ── born-effective gate (DEC-1) ──────────────────────────────────
        auth_actor = cmd.delegated_by_user_id or cmd.decided_by_user_id
        auth = self._authorize_ops(auth_actor, cmd, auth_targets)
        conf_ok = (cmd.created_from in (CreatedFrom.MARKER, CreatedFrom.DASHBOARD)
                   or (cmd.confidence is not None and cmd.confidence >= self.tau))

        hold_reason: str | None = None
        hold_extra: dict = {}
        if cmd.relayed:
            hold_reason = "relayed"  # claimed maker not among cited authors
        elif not conf_ok:
            hold_reason = "below_tau"  # G19 confidence gate — never silently dropped
        elif not auth.allowed:
            hold_reason = "unauthorized"
            hold_extra = {"authority_basis": auth.basis}
        else:
            # rank gate (G10) + peer-conflict hold (§Facets) per standing occupant
            actor_rank = self.org.rank_of(cmd.decided_by_user_id)
            for unit, occupant in occupants.items():
                if not self.authority.rank_gate_ok(cmd.decided_by_user_id,
                                                   occupant.decided_by_role_at_time):
                    hold_reason = "rank_gate"
                    hold_extra = {"unit": unit, "standing_decision_id": occupant.id,
                                  "standing_maker": occupant.decided_by_user_id}
                    break
                if (actor_rank == occupant.decided_by_role_at_time
                        and occupant.decided_by_user_id != cmd.decided_by_user_id
                        and not self.authority.comparable(cmd.decided_by_user_id,
                                                          occupant.decided_by_user_id)):
                    hold_reason = "peer_hold"  # incomparable ranks -> explicit human tiebreak
                    hold_extra = {"unit": unit, "standing_decision_id": occupant.id,
                                  "peers": [cmd.decided_by_user_id,
                                            occupant.decided_by_user_id]}
                    break

        # DEC-8 effect-window overlap [EVM-004]: the later one is held proposed
        if hold_reason is None and cmd.effect_window is not None:
            overlap = self._overlapping_window(cmd, plan)
            if overlap is not None:
                hold_reason = "overlap_hold"
                hold_extra = {"overlaps_decision_id": overlap.id}

        rank_snapshot = self.org.rank_of(cmd.decided_by_user_id)

        if hold_reason is None:
            # ING-7/G31: an older same-unit decision is born ALREADY-SUPERSEDED —
            # it enters history without disturbing the present
            candidate_key = self._sort_key(
                ts, recorded_at,
                f"msg:{cmd.source_message_id}" if cmd.source_message_id is not None
                else f"cmd:{cmd.client_command_id}")
            newer = [d for d in occupants.values() if self._decision_key(d) > candidate_key]
            if newer:
                standing = max(newer, key=self._decision_key)
                decision = self._insert_decision(
                    cmd, ts=ts, recorded_at=recorded_at,
                    status=DecisionStatus.SUPERSEDED, plan=plan,
                    rank_snapshot=rank_snapshot,
                    approval_via=(ApprovalVia.DELEGATION
                                  if cmd.delegated_by_user_id is not None else None),
                    approved_by=cmd.delegated_by_user_id)
                decision.superseded_by_decision_id = standing.id
                self._emit("decision_born_superseded", "decision", decision.id,
                           self._decision_payload(decision, superseded_by=standing.id),
                           ts, cmd)
                return {"status": "already_superseded", "decision_id": decision.id,
                        "superseded_by": standing.id}

            decision = self._insert_decision(
                cmd, ts=ts, recorded_at=recorded_at, status=DecisionStatus.EFFECTIVE,
                plan=plan, rank_snapshot=rank_snapshot,
                approval_via=(ApprovalVia.DELEGATION
                              if cmd.delegated_by_user_id is not None else None),
                approved_by=cmd.delegated_by_user_id)
            if cmd.effect_window is not None:
                # G42: shadows the standing decision inside its window — occupies
                # nothing, supersedes nothing, auto-un-shadows after
                self._emit("decision_effective", "decision", decision.id,
                           self._decision_payload(decision, windowed=True,
                                                  new_task_id=new_task_id,
                                                  project_id=self._context_project(cmd)),
                           ts, cmd)
                return {"status": "effective", "decision_id": decision.id,
                        "windowed": True}
            write = self._effective_write(decision, plan, cmd)
            self._emit("decision_effective", "decision", decision.id,
                       self._decision_payload(decision, new_task_id=new_task_id,
                                              project_id=self._context_project(cmd),
                                              **write),
                       ts, cmd)
            return {"status": "effective", "decision_id": decision.id,
                    "new_task_id": new_task_id, **write}

        # ── proposal lane ────────────────────────────────────────────────
        # DEC-7/G49 dedup-merge: same (unit, op, value) pending => merge into it
        # (windowed proposals stay separate — a window is part of the meaning)
        merged_into = (self._find_pending_twin(plan)
                       if cmd.effect_window is None else None)
        if merged_into is not None:
            for citation in cmd.citations:
                self._add_citation_once(merged_into.id, citation, citation.kind)
            self._emit("proposal_merged", "decision", merged_into.id,
                       {"into": merged_into.id, "proposer": cmd.decided_by_user_id,
                        "message_ids": [c.message_id for c in cmd.citations]},
                       ts, cmd)
            return {"status": "merged_into_pending", "decision_id": merged_into.id}

        decision = self._insert_decision(
            cmd, ts=ts, recorded_at=recorded_at, status=DecisionStatus.PROPOSED,
            plan=plan, rank_snapshot=rank_snapshot)
        # stamp the task-creation context so approval can re-emit it
        decision.new_task_id = new_task_id
        decision.context_project_id = self._context_project(cmd)

        # settled #17b: the proposer's own different-value pending on a shared
        # unit is withdrawn, linked to the newer proposal
        withdrawn = self._withdraw_own_older(decision, plan, cmd)

        approvers = auth.approvers or self._fallback_approvers(cmd, occupants, hold_reason)
        self._emit("decision_proposed", "decision", decision.id,
                   self._decision_payload(decision, hold_reason=hold_reason,
                                          approvers=approvers,
                                          new_task_id=new_task_id,
                                          project_id=self._context_project(cmd),
                                          withdrawn=withdrawn, **hold_extra),
                   ts, cmd)
        return {"status": "proposed", "decision_id": decision.id,
                "hold_reason": hold_reason, "approvers": approvers,
                "new_task_id": new_task_id, "withdrawn": withdrawn, **hold_extra}

    # ── propose helpers ──────────────────────────────────────────────────

    def _context_project(self, cmd: ProposeDecision) -> int | None:
        if cmd.context_group_id is not None:
            group = self.org.get_group(cmd.context_group_id)
            if group is not None:
                return group.project_id
        return None

    def _authorize_ops(self, actor_id: int, cmd: ProposeDecision,
                       targets: list[str] | None = None):
        """DEC-9/[EVM-003]: all-or-nothing — allowed iff the actor clears the
        HIGHEST authority any op requires (i.e. every target). `targets` are
        the pre-rewrite op targets (may contain NEW_TASK)."""
        results = []
        if targets is None:
            targets = sorted({op.target for op in cmd.ops} or {cmd.scope_target})
        for target in targets:
            results.append(self.authority.can_decide_target(
                actor_id, cmd.scope, target, cmd.context_group_id))
        allowed = all(r.allowed for r in results)
        basis = "; ".join(r.basis for r in results)
        approvers: list[int] = []
        for r in results:
            for a in r.approvers:
                if a not in approvers:
                    approvers.append(a)
        return AuthorityDecision(allowed=allowed, basis=basis, approvers=approvers)

    def _occupant_value(self, occupant: Decision, unit: str) -> tuple[str, str] | None:
        plan = derive_unit_plan([OpSpec(**op) for op in occupant.ops])
        return plan.unit_values.get(unit)

    def _version_conflict(self, expected: str, plan: UnitPlan,
                          occupants: dict[str, Decision]) -> dict | None:
        """[EVM-021]: `expected` is the standing same-unit effective decision id
        the form was rendered against ("vacant" when it showed none). Any
        mismatch ⇒ 409-shaped diff card, never a silent overwrite."""
        current_ids = {str(d.id) for d in occupants.values()}
        ok = (not current_ids) if expected == EXPECTED_VACANT else (expected in current_ids)
        if ok:
            return None
        diff = [{"unit": unit, "current_decision_id": occupant.id,
                 "current_value": self._occupant_value(occupant, unit)}
                for unit, occupant in occupants.items()]
        return {"status": "version_conflict", "expected_version": expected,
                "diff": diff}

    def _overlapping_window(self, cmd: ProposeDecision, plan: UnitPlan) -> Decision | None:
        if cmd.effect_window is None:
            return None
        start, until = (_as_utc(cmd.effect_window[0]), _as_utc(cmd.effect_window[1]))
        return self._overlapping_window_for(start, until, plan.occupied_units)

    def _overlapping_window_for(self, start: datetime | None, until: datetime | None,
                                units: list[str],
                                exclude_id: int | None = None) -> Decision | None:
        if start is None or until is None:
            return None
        rows = self.session.execute(
            select(Decision, DecisionUnit.unit_key)
            .join(DecisionUnit, DecisionUnit.decision_id == Decision.id)
            .where(Decision.status == DecisionStatus.EFFECTIVE,
                   Decision.effect_window_from.is_not(None))
        ).all()
        for decision, unit_key in rows:
            if decision.id == exclude_id or unit_key not in units:
                continue
            if (decision.effect_window_from <= until
                    and start <= decision.effect_window_until):
                return decision
        return None

    def _find_pending_twin(self, plan: UnitPlan) -> Decision | None:
        if not plan.occupied_units:
            return None
        candidates = self.session.scalars(
            select(Decision)
            .join(DecisionUnit, DecisionUnit.decision_id == Decision.id)
            .where(Decision.status == DecisionStatus.PROPOSED,
                   DecisionUnit.unit_key == plan.occupied_units[0])
        ).unique()
        for candidate in candidates:
            if candidate.effect_window_from is not None:
                continue
            other = derive_unit_plan([OpSpec(**op) for op in candidate.ops])
            if (set(other.occupied_units) == set(plan.occupied_units)
                    and other.unit_values == plan.unit_values):
                return candidate
        return None

    def _withdraw_own_older(self, new: Decision, plan: UnitPlan,
                            cmd: ProposeDecision) -> list[int]:
        withdrawn: list[int] = []
        rows = self.session.execute(
            select(Decision, DecisionUnit.unit_key)
            .join(DecisionUnit, DecisionUnit.decision_id == Decision.id)
            .where(Decision.status == DecisionStatus.PROPOSED,
                   Decision.decided_by_user_id == cmd.decided_by_user_id,
                   Decision.id != new.id)
        ).all()
        for decision, unit_key in rows:
            if unit_key not in plan.occupied_units or decision.id in withdrawn:
                continue
            value = self._occupant_value(decision, unit_key)
            if value is not None and value != plan.unit_values.get(unit_key):
                decision.status = DecisionStatus.REJECTED
                decision.rejected_reason = RejectedReason.WITHDRAWN
                decision.superseded_by_decision_id = new.id
                withdrawn.append(decision.id)
                self._emit("proposal_withdrawn", "decision", decision.id,
                           {"decision_id": decision.id, "replaced_by": new.id,
                            "proposer": cmd.decided_by_user_id},
                           new.ts, cmd)
        return withdrawn

    def _fallback_approvers(self, cmd: ProposeDecision,
                            occupants: dict[str, Decision],
                            hold_reason: str | None) -> list[int]:
        if hold_reason == "relayed" or hold_reason == "below_tau":
            # tagged to the claimed maker (self-confirm) + the unit's authority
            approvers = [cmd.decided_by_user_id]
        else:
            approvers = []
        for occupant in occupants.values():
            if occupant.decided_by_user_id not in approvers:
                approvers.append(occupant.decided_by_user_id)
        return approvers

    def _add_citation_once(self, decision_id: int, citation: CitationSpec,
                           kind: CitationKind) -> None:
        exists = self.session.scalar(
            select(DecisionCitation).where(
                DecisionCitation.decision_id == decision_id,
                DecisionCitation.message_id == citation.message_id,
                DecisionCitation.kind == kind,
            )
        )
        if exists is None:
            self.session.add(DecisionCitation(
                decision_id=decision_id, message_id=citation.message_id, kind=kind,
                rev_at_capture=citation.rev_at_capture, rev_at_act=citation.rev_at_act,
            ))

    # ══════════════════════════════════════════════════════ approve (DEC-5 act half, G52, EVM-005)

    def _approve(self, cmd: ApproveProposal) -> dict:
        decision = self.session.get(Decision, cmd.decision_id)
        if decision is None:
            return {"status": "not_found", "decision_id": cmd.decision_id}
        if decision.status is not DecisionStatus.PROPOSED:
            return {"status": f"already_{decision.status.value}",
                    "decision_id": decision.id}

        ops = [OpSpec(**op) for op in decision.ops]
        plan = derive_unit_plan(ops)
        occupants = self._standing_occupants(plan.occupied_units, plan.displaced_prefixes)

        # G52 approval-time revalidation: re-check targets NOW before anything
        # takes effect
        issues = self._revalidation_issues(decision, plan, occupants)
        if issues and not cmd.ack_revalidation:
            return {"status": "revalidation_required", "decision_id": decision.id,
                    "issues": issues}

        approver = cmd.approved_by_user_id
        if approver == decision.decided_by_user_id:
            # self-confirm lane (below-tau / relayed): valid iff the maker holds
            # the unit's authority
            auth = self._authorize_decision_targets(approver, decision)
            via = ApprovalVia.SELF_CONFIRM
        else:
            auth = self._authorize_decision_targets(approver, decision)
            via = ApprovalVia.AUTHORITY
        if not auth.allowed:
            # failed approval attempt stays visible to its actor (design-v2
            # §Proposal hygiene) — surface as outcome, no state change
            return {"status": "forbidden", "decision_id": decision.id,
                    "basis": auth.basis, "approvers": auth.approvers}
        for occupant in occupants.values():
            if not self.authority.rank_gate_ok(approver, occupant.decided_by_role_at_time):
                return {"status": "forbidden", "decision_id": decision.id,
                        "basis": f"rank gate vs standing decision {occupant.id}",
                        "approvers": auth.approvers}

        # [EVM-005] authority evaluated AT ACT TIME, snapshotted on the act
        decision.approved_by_user_id = approver
        decision.approval_via = via
        decision.approved_by_role_at_act = self.org.rank_of(approver)
        decision.status = DecisionStatus.EFFECTIVE
        if cmd.rev_at_act is not None:
            # bind the act to the revision the approver saw (G65)
            for row in self.session.scalars(select(DecisionCitation).where(
                    DecisionCitation.decision_id == decision.id,
                    DecisionCitation.kind == CitationKind.APPROVAL)):
                row.rev_at_act = cmd.rev_at_act
        if cmd.source_message_id is not None:
            self._add_citation_once(
                decision.id,
                CitationSpec(message_id=cmd.source_message_id,
                             kind=CitationKind.APPROVAL, rev_at_capture=1,
                             rev_at_act=cmd.rev_at_act),
                CitationKind.APPROVAL)

        # NEW_TASK proposals: replay the creation context stamped at propose
        # time, so the consumer materializes the task under its real project
        task_ctx = ({"new_task_id": decision.new_task_id,
                     "project_id": decision.context_project_id}
                    if decision.new_task_id is not None else {})

        if decision.effect_window_from is not None:
            self._emit("decision_effective", "decision", decision.id,
                       self._decision_payload(decision, windowed=True,
                                              approved_by=approver, via=via.value,
                                              **task_ctx),
                       decision.ts, cmd)
            return {"status": "effective", "decision_id": decision.id, "windowed": True}

        write = self._effective_write(decision, plan, cmd)
        self._emit("decision_effective", "decision", decision.id,
                   self._decision_payload(decision, approved_by=approver,
                                          via=via.value, **task_ctx, **write),
                   decision.ts, cmd)
        return {"status": "effective", "decision_id": decision.id, "via": via.value,
                **task_ctx, **write}

    def _authorize_decision_targets(self, actor_id: int, decision: Decision):
        targets = {op["target"] for op in decision.ops} or {decision.scope_target}
        results = [self.authority.can_decide_target(actor_id, decision.scope, t, None)
                   for t in sorted(targets)]
        approvers: list[int] = []
        for r in results:
            for a in r.approvers:
                if a not in approvers:
                    approvers.append(a)
        return AuthorityDecision(allowed=all(r.allowed for r in results),
                                 basis="; ".join(r.basis for r in results),
                                 approvers=approvers)

    def _revalidation_issues(self, decision: Decision, plan: UnitPlan,
                             occupants: dict[str, Decision]) -> list[dict]:
        issues: list[dict] = []
        if self.task_port is not None:
            for task_id in plan.task_ids:
                view = self.task_port.get_task_view(task_id)
                if view is None:
                    continue
                if view.status is TaskStatus.CANCELED:
                    canceling = self.session.scalar(
                        select(EffectiveUnit.decision_id)
                        .where(EffectiveUnit.unit_key == f"task:{task_id}|status"))
                    issues.append({"kind": "target_canceled", "task_id": task_id,
                                   "canceling_decision_id": canceling,
                                   "options": ["approve_as_revive", "dismiss"]})
                elif view.status is TaskStatus.MERGED:
                    issues.append({"kind": "target_merged", "task_id": task_id,
                                   "survivor_task_id": view.merged_into,
                                   "options": ["redirect_to_survivor"]})
        for unit, occupant in occupants.items():
            if occupant.recorded_at > decision.recorded_at:
                issues.append({"kind": "value_moved", "unit": unit,
                               "current_decision_id": occupant.id,
                               "current_value": self._occupant_value(occupant, unit)})
        if decision.effect_window_from is not None:
            # [EVM-004] re-check at act time: another window may have gone
            # effective on this unit while the proposal waited
            overlap = self._overlapping_window_for(
                decision.effect_window_from, decision.effect_window_until,
                plan.occupied_units, exclude_id=decision.id)
            if overlap is not None:
                issues.append({"kind": "window_overlap",
                               "overlaps_decision_id": overlap.id})
        return issues

    # ══════════════════════════════════════════════════════ reject (DEC-6)

    def _reject(self, cmd: RejectProposal) -> dict:
        decision = self.session.get(Decision, cmd.decision_id)
        if decision is None:
            return {"status": "not_found", "decision_id": cmd.decision_id}
        actor = cmd.rejected_by_user_id
        is_maker = actor == decision.decided_by_user_id
        rank_ok = self.org.rank_of(actor) >= decision.decided_by_role_at_time

        if decision.status is DecisionStatus.PROPOSED:
            allowed = (is_maker or rank_ok
                       or self._authorize_decision_targets(actor, decision).allowed)
            if not allowed:
                self._emit("challenge_filed", "decision", decision.id,
                           {"decision_id": decision.id, "challenger": actor,
                            "resolves_to": decision.decided_by_user_id},
                           _utcnow(), cmd)
                return {"status": "challenge_filed", "decision_id": decision.id}
            reason = (RejectedReason.VETO if cmd.reason == "veto"
                      else RejectedReason.DISMISSED)
            decision.status = DecisionStatus.REJECTED
            decision.rejected_reason = reason
            self._emit("decision_rejected", "decision", decision.id,
                       {"decision_id": decision.id, "rejected_reason": reason.value,
                        "by": actor}, _utcnow(), cmd)
            return {"status": "rejected", "decision_id": decision.id,
                    "reason": reason.value}

        if decision.status is DecisionStatus.EFFECTIVE:
            # veto of a standing decision: maker or rank >= maker; others file a
            # challenge the maker resolves (G18)
            if not (is_maker or rank_ok):
                self._emit("challenge_filed", "decision", decision.id,
                           {"decision_id": decision.id, "challenger": actor,
                            "resolves_to": decision.decided_by_user_id},
                           _utcnow(), cmd)
                return {"status": "challenge_filed", "decision_id": decision.id}
            decision.status = DecisionStatus.REJECTED
            decision.rejected_reason = RejectedReason.VETO
            # vacate every unit it occupies
            for row in list(self.session.scalars(select(EffectiveUnit).where(
                    EffectiveUnit.decision_id == decision.id))):
                self.session.delete(row)
            self.session.flush()
            # G17 resurrection: restore each decision it superseded iff no other
            # effective same-unit superseder remains, then refold
            resurrected = self._resurrect_predecessors(decision, cmd)
            self._emit("decision_rejected", "decision", decision.id,
                       {"decision_id": decision.id, "rejected_reason": "veto",
                        "by": actor, "resurrected": resurrected,
                        "retraction": True},  # feed retraction entries (G20)
                       _utcnow(), cmd)
            return {"status": "rejected", "decision_id": decision.id,
                    "reason": "veto", "resurrected": resurrected}

        return {"status": f"already_{decision.status.value}", "decision_id": decision.id}

    def _resurrect_predecessors(self, rejected: Decision, cmd: CommandEnvelope) -> list[int]:
        resurrected: list[int] = []
        predecessors = list(self.session.scalars(select(Decision).where(
            Decision.superseded_by_decision_id == rejected.id,
            Decision.status == DecisionStatus.SUPERSEDED)))
        for predecessor in predecessors:
            units = self._units_of(predecessor.id)
            vacant = all(
                self.session.scalar(select(EffectiveUnit).where(
                    EffectiveUnit.unit_key == unit)) is None
                for unit in units
            )
            if not vacant:
                continue
            predecessor.status = DecisionStatus.EFFECTIVE
            predecessor.superseded_by_decision_id = None
            if predecessor.effect_window_from is None:
                for unit in units:
                    self.session.add(EffectiveUnit(unit_key=unit,
                                                   decision_id=predecessor.id))
            resurrected.append(predecessor.id)
            self._emit("decision_resurrected", "decision", predecessor.id,
                       self._decision_payload(predecessor,
                                              resurrected_by_rejection_of=rejected.id),
                       _utcnow(), cmd)
        self.session.flush()
        return resurrected

    # ══════════════════════════════════════════════════════ bulk (DEC-7)

    def _bulk(self, cmd: BulkProposalAction) -> dict:
        pendings = list(self.session.scalars(select(Decision).where(
            Decision.status == DecisionStatus.PROPOSED)))
        acted: list[int] = []
        skipped: list[dict] = []
        for decision in pendings:
            if cmd.action == "dismiss_all_from" and (
                    decision.decided_by_user_id != cmd.from_user_id):
                continue
            if cmd.action == "dismiss_stale":
                age_days = (_utcnow() - decision.recorded_at).days
                if age_days < (cmd.stale_days or 14):
                    continue
            auth = self._authorize_decision_targets(cmd.actor_user_id, decision)
            if not auth.allowed:
                continue
            if cmd.action == "approve_all":
                outcome = self._approve(ApproveProposal(
                    client_command_id=cmd.client_command_id, persona=cmd.persona,
                    created_from=cmd.created_from, decision_id=decision.id,
                    approved_by_user_id=cmd.actor_user_id))
                if outcome["status"] == "effective":
                    acted.append(decision.id)
                else:
                    skipped.append({"decision_id": decision.id, **outcome})
            else:
                decision.status = DecisionStatus.REJECTED
                decision.rejected_reason = RejectedReason.DISMISSED
                self._emit("decision_rejected", "decision", decision.id,
                           {"decision_id": decision.id, "rejected_reason": "dismissed",
                            "by": cmd.actor_user_id, "bulk": cmd.action},
                           _utcnow(), cmd)
                acted.append(decision.id)
        return {"status": "bulk_done", "action": cmd.action,
                "acted": acted, "skipped": skipped}

    # ═══════════════════════════════════ task updates & signals (gateway side)

    def _record_task_update(self, cmd: RecordTaskUpdate) -> dict:
        ts = _as_utc(cmd.ts) or _utcnow()
        task_id = cmd.task_id
        port = self.task_port
        view = port.get_task_view(task_id) if port else None

        if port and view is not None and view.status is TaskStatus.MERGED and view.merged_into:
            # ops aimed at a merged husk auto-redirect to the survivor (G52)
            task_id = view.merged_into
            view = port.get_task_view(task_id)

        if view is not None and view.status is TaskStatus.CANCELED:
            # TSK-6 terminal lock: notes only; status attempts get the canceling
            # decision named
            if cmd.update_kind == "status":
                canceling = self.session.scalar(
                    select(EffectiveUnit.decision_id)
                    .where(EffectiveUnit.unit_key == f"task:{task_id}|status"))
                return {"status": "terminal_locked", "task_id": task_id,
                        "canceling_decision_id": canceling,
                        "hint": "reopen requires a lead `revive` decision"}

        if view is not None and cmd.actor_user_id in view.pic_user_ids:
            lane = "pic_auto"  # the review's carve-out (G7)
        elif self.authority.can_decide_target(
                cmd.actor_user_id, DecisionScope.TASK, f"task:{task_id}", None).allowed:
            lane = "authority"  # decision-grade status change
        else:
            # anyone else: a PIC gets a confirm card; their tap applies it (G9)
            self._emit("task_update_pending_confirm", "task_update", task_id,
                       {"task_id": task_id, "actor_user_id": cmd.actor_user_id,
                        "update_kind": cmd.update_kind, "payload": cmd.payload,
                        "ts": _iso(ts), "source_message_id": cmd.source_message_id,
                        "confirmers": view.pic_user_ids if view else []},
                       ts, cmd)
            return {"status": "pending_confirm", "task_id": task_id,
                    "confirmers": view.pic_user_ids if view else []}

        self._emit("task_update_recorded", "task_update", task_id,
                   {"task_id": task_id, "actor_user_id": cmd.actor_user_id,
                    "update_kind": cmd.update_kind, "payload": cmd.payload,
                    "lane": lane, "ts": _iso(ts),
                    "created_from": cmd.created_from.value,
                    "confidence": cmd.confidence,
                    "source_message_id": cmd.source_message_id},
                   ts, cmd)
        return {"status": "applied", "task_id": task_id, "lane": lane}

    def _record_signal(self, cmd: RecordSignal) -> dict:
        ts = _as_utc(cmd.ts) or _utcnow()
        # identity key [EVM-013] rides in the payload; B's ledger folds/dedups
        self._emit("signal_recorded", "signal", cmd.task_id or 0,
                   {"signal_kind": cmd.signal_kind, "project_id": cmd.project_id,
                    "task_id": cmd.task_id, "party_id": cmd.party_id,
                    "normalized_topic": cmd.normalized_topic, "excerpt": cmd.excerpt,
                    "message_id": cmd.source_message_id, "ts": _iso(ts),
                    "window_id": cmd.window_id},
                   ts, cmd)
        return {"status": "signal_recorded"}

    def _append_corroboration(self, cmd: AppendCorroboration) -> dict:
        decision = self.session.get(Decision, cmd.decision_id)
        if decision is None:
            return {"status": "not_found", "decision_id": cmd.decision_id}
        self._add_citation_once(decision.id, cmd.citation, CitationKind.CORROBORATION)
        self._emit("corroboration_appended", "decision", decision.id,
                   {"decision_id": decision.id,
                    "message_ids": [cmd.citation.message_id]},
                   _as_utc(cmd.ts) or _utcnow(), cmd)
        return {"status": "corroborated", "decision_ids": [decision.id]}

    # ══════════════════════════════════════════════ interface #8 (work-split)

    def tracked_message_ids(self) -> set[int]:
        """Reaction acts are recorded ONLY on tracked messages — the source
        messages of pending records (G67). `connectors` (B) consults this
        before writing a `reaction_acts` row."""
        rows = self.session.execute(
            select(DecisionCitation.message_id)
            .join(Decision, Decision.id == DecisionCitation.decision_id)
            .where(Decision.status == DecisionStatus.PROPOSED)
        ).scalars()
        return set(rows)

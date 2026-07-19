"""DEC-4 — the authority gate (design-v2 §Hierarchy & authority).

`can_decide(actor, unit)` is a TOTAL function (G48): every unit resolves to a
defined authority set, including team-less tasks, unknown targets, and rootless
orgs. Authority is evaluated AT ACT TIME and snapshotted on the act by the
caller [EVM-005] — nothing here stores state.

Rules implemented:
- task-scoped: actor is over ANY owning team of the task — the team's lead or
  anyone in the manager chain above that lead, or the coordinator (rank 3).
- NEW_TASK: checked against the chat group's team (G3); for project-wide groups,
  any team the actor leads in that project.
- team-less tasks (G48): project-level — any lead of that project decides;
  coordinator = supersession apex.
- team policy: that team's lead+ (lead, their chain, coordinator).
- project policy: coordinator; leads may propose (all-leads joint approval is
  the hard-coded multi-party case — MVP: coordinator approval effects it;
  all-leads reducer = roadmap [EVM-019]).
- rootless fallback (G37): no coordinator ⇒ the leads of the involved teams
  jointly hold apex; peer-conflict holds are the caller's job (§Facets).
"""
from __future__ import annotations

from dataclasses import dataclass

from evermind.contracts.enums import DecisionScope
from evermind.contracts.ports import TaskReadPort
from evermind.org.service import OrgService


@dataclass
class AuthorityDecision:
    allowed: bool
    basis: str  # human-readable reason, rendered on cards/receipts
    approvers: list[int]  # who could approve if not allowed (inbox routing)


class AuthorityService:
    def __init__(self, org: OrgService, task_port: TaskReadPort | None = None):
        self.org = org
        self.task_port = task_port

    # ── helpers ──────────────────────────────────────────────────────────

    def _is_coordinator(self, user_id: int) -> bool:
        return self.org.rank_of(user_id) >= 3

    def _over_team(self, actor_id: int, team_id: int) -> bool:
        """Lead of the team, or in the manager chain above the lead."""
        if self._is_coordinator(actor_id):
            return True
        lead = self.org.lead_of_team(team_id)
        if lead is None:
            return False
        if actor_id == lead:
            return True
        return self.org.is_ancestor(actor_id, lead)

    def team_approvers(self, team_id: int) -> list[int]:
        """Public read for callers routing reviews to a team (lead + coordinator)
        — e.g. signal-promotion approvals (harvest of PR #53)."""
        return self._team_approvers(team_id)

    def _team_approvers(self, team_id: int) -> list[int]:
        approvers: list[int] = []
        lead = self.org.lead_of_team(team_id)
        if lead is not None:
            approvers.append(lead)
        coordinator = self.org.coordinator()
        if coordinator is not None and coordinator.id not in approvers:
            approvers.append(coordinator.id)
        return approvers

    def _project_leads_plus_coordinator(self, project_id: int) -> list[int]:
        approvers = self.org.leads_of_project(project_id)
        coordinator = self.org.coordinator()
        if coordinator is not None and coordinator.id not in approvers:
            approvers.append(coordinator.id)
        return approvers

    def _task_teams(self, task_id: int) -> tuple[list[int], int | None]:
        """(owning team ids, project id) via the read-only tasks port
        (interface #9). Unknown task ⇒ ([], None)."""
        if self.task_port is None:
            return [], None
        view = self.task_port.get_task_view(task_id)
        if view is None:
            return [], None
        return list(view.team_ids), view.project_id

    # ── the gate ─────────────────────────────────────────────────────────

    def can_decide_target(
        self,
        actor_id: int,
        scope: DecisionScope,
        target: str,
        context_group_id: int | None = None,
    ) -> AuthorityDecision:
        """Total: always returns an answer with a defined approver set (G48)."""
        if scope is DecisionScope.TEAM or target.startswith("team:"):
            team_id = int(target.split(":", 1)[1]) if target.startswith("team:") else None
            if team_id is None:
                return AuthorityDecision(False, "team target unresolved", self._apex())
            if self._over_team(actor_id, team_id):
                return AuthorityDecision(True, f"lead+ of team {team_id}", [])
            return AuthorityDecision(False, f"team policy needs team {team_id} lead+",
                                     self._team_approvers(team_id))

        if scope is DecisionScope.PROJECT or target.startswith("project:"):
            project_id = (int(target.split(":", 1)[1])
                          if target.startswith("project:") else None)
            if self._is_coordinator(actor_id):
                return AuthorityDecision(True, "coordinator", [])
            approvers = (self._project_leads_plus_coordinator(project_id)
                         if project_id is not None else self._apex())
            return AuthorityDecision(
                False, "project policy needs the coordinator (or all leads jointly)",
                approvers)

        # task scope
        if target == "NEW_TASK":
            return self._can_decide_new_task(actor_id, context_group_id)
        if target.startswith("task:"):
            return self._can_decide_task(actor_id, int(target.split(":", 1)[1]))
        # unknown target class — total function fallback: apex only
        if self._is_coordinator(actor_id):
            return AuthorityDecision(True, "coordinator (unresolved target)", [])
        return AuthorityDecision(False, f"unresolved target {target!r}", self._apex())

    def _can_decide_task(self, actor_id: int, task_id: int) -> AuthorityDecision:
        team_ids, project_id = self._task_teams(task_id)
        if team_ids:
            for team_id in team_ids:
                if self._over_team(actor_id, team_id):
                    return AuthorityDecision(True, f"over owning team {team_id}", [])
            approvers: list[int] = []
            for team_id in team_ids:
                for approver in self._team_approvers(team_id):
                    if approver not in approvers:
                        approvers.append(approver)
            return AuthorityDecision(False, f"task {task_id} needs an owning team's lead+",
                                     approvers)
        # team-less (G48): project-level governance
        if project_id is not None:
            if self._is_coordinator(actor_id) or actor_id in self.org.leads_of_project(project_id):
                return AuthorityDecision(True, "project-level (team-less task)", [])
            return AuthorityDecision(False, "team-less task needs a project lead",
                                     self._project_leads_plus_coordinator(project_id))
        # task unknown to the projection (or no port wired): apex fallback
        if self._is_coordinator(actor_id):
            return AuthorityDecision(True, "coordinator (task not in projection)", [])
        return AuthorityDecision(False, f"task {task_id} not in projection", self._apex())

    def _can_decide_new_task(
        self, actor_id: int, context_group_id: int | None
    ) -> AuthorityDecision:
        if context_group_id is not None:
            group = self.org.get_group(context_group_id)
            if group is not None:
                if group.team_id is not None:
                    if self._over_team(actor_id, group.team_id):
                        return AuthorityDecision(True, "over the group's team (G3)", [])
                    return AuthorityDecision(False, "NEW_TASK needs the group's team lead+",
                                             self._team_approvers(group.team_id))
                # project-wide group: any team the actor leads in that project
                led = set(self.org.teams_led_by(actor_id))
                project_team_leads = {
                    self.org.lead_of_team(t)
                    for t in led
                    if self.org.project_of_team(t) == group.project_id
                }
                if self._is_coordinator(actor_id) or (led and actor_id in project_team_leads):
                    return AuthorityDecision(True, "leads a team in the project-wide group", [])
                return AuthorityDecision(
                    False, "NEW_TASK in a project-wide group needs a lead",
                    self._project_leads_plus_coordinator(group.project_id))
        if self._is_coordinator(actor_id):
            return AuthorityDecision(True, "coordinator", [])
        return AuthorityDecision(False, "NEW_TASK without group context needs apex",
                                 self._apex())

    def _apex(self) -> list[int]:
        """Coordinator, or (rootless fallback, G37) every lead in the org."""
        coordinator = self.org.coordinator()
        if coordinator is not None:
            return [coordinator.id]
        leads: list[int] = []
        for persona in self.org.list_personas():
            if persona.role_rank >= 2 and persona.id not in leads:
                leads.append(persona.id)
        return leads

    # ── rank machinery (G10 gate + peer comparability) ───────────────────

    def rank_gate_ok(self, actor_id: int, old_maker_rank_snapshot: int) -> bool:
        """Supersession gate: rank(actor) ≥ rank(old maker, snapshotted)."""
        return self.org.rank_of(actor_id) >= old_maker_rank_snapshot

    def comparable(self, actor_id: int, other_id: int) -> bool:
        """Two actors are comparable when one sits in the other's manager chain
        (or they are the same person). Equal-rank incomparable actors are PEERS
        — a second same-unit effective write from a peer is held `proposed`
        (§Facets peer-conflict; the caller applies the hold)."""
        if actor_id == other_id:
            return True
        return self.org.is_ancestor(actor_id, other_id) or self.org.is_ancestor(other_id, actor_id)

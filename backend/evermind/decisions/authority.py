"""Authority resolution over the org and injected task read ports (DEC-4)."""

from __future__ import annotations

from enum import Enum

from evermind.decisions.task_state import TaskStatePort
from evermind.org.service import OrgService


def target_from_unit_key(unit_key: str) -> str | None:
    parts = unit_key.split("|", 2)
    if len(parts) >= 2 and parts[0] == "v1":
        return parts[1]
    return unit_key if ":" in unit_key else None


class AuthorityComparison(str, Enum):
    GREATER = "greater"
    EQUAL = "equal"
    LESS = "less"
    INCOMPARABLE = "incomparable"


class AuthorityResolver:
    def __init__(self, org: OrgService, task_state: TaskStatePort):
        self.org = org
        self.task_state = task_state

    def can_decide(self, actor_user_id: int, unit_key: str) -> bool:
        actor = self.org.get_user(actor_user_id)
        target = target_from_unit_key(unit_key)
        if actor is None or target is None:
            return False
        kind, separator, raw_id = target.partition(":")
        if not separator or not raw_id.isdecimal():
            return False
        target_id = int(raw_id)
        if kind == "task":
            return self._can_decide_task(actor_user_id, target_id)
        if kind == "team":
            return self._can_decide_team(actor_user_id, target_id)
        if kind == "project":
            return (
                self.org.rank_of(actor_user_id) >= 3 and self.org.get_project(target_id) is not None
            )
        return False

    def compare_to_snapshot(
        self,
        actor_user_id: int,
        prior_user_id: int,
        prior_rank: int,
    ) -> AuthorityComparison:
        actor_rank = self.org.rank_of(actor_user_id)
        if actor_rank == 0:
            return AuthorityComparison.LESS
        if actor_user_id == prior_user_id:
            return AuthorityComparison.EQUAL
        if actor_user_id in self.org.manager_chain(prior_user_id):
            return AuthorityComparison.GREATER
        if prior_user_id in self.org.manager_chain(actor_user_id):
            return AuthorityComparison.LESS
        if actor_rank >= 3 and prior_rank < actor_rank:
            return AuthorityComparison.GREATER
        if prior_rank >= 3 and actor_rank < prior_rank:
            return AuthorityComparison.LESS
        return AuthorityComparison.INCOMPARABLE

    def _can_decide_task(self, actor_user_id: int, task_id: int) -> bool:
        task = self.task_state.get_task(task_id)
        if task is None:
            return False
        if task.owning_team_ids:
            return any(
                self._can_decide_team(actor_user_id, team_id) for team_id in task.owning_team_ids
            )
        return actor_user_id in self.org.lead_user_ids_for_project(task.project_id) or (
            self.org.rank_of(actor_user_id) >= 3
        )

    def _can_decide_team(self, actor_user_id: int, team_id: int) -> bool:
        if self.org.get_team(team_id) is None:
            return False
        if self.org.rank_of(actor_user_id) >= 3:
            return True
        for lead_user_id in self.org.lead_user_ids_for_team(team_id):
            if actor_user_id == lead_user_id:
                return True
            if actor_user_id in self.org.manager_chain(lead_user_id):
                return True
        return False

    def required_approver_ids(self, unit_keys: list[str]) -> set[int]:
        approvers: set[int] = set()
        for unit_key in unit_keys:
            target = target_from_unit_key(unit_key)
            if target is None:
                continue
            kind, separator, raw_id = target.partition(":")
            if not separator or not raw_id.isdecimal():
                continue
            target_id = int(raw_id)
            if kind == "team":
                approvers.update(self.org.lead_user_ids_for_team(target_id))
            elif kind == "project":
                approvers.update(self.org.coordinator_user_ids())
            elif kind == "task":
                task = self.task_state.get_task(target_id)
                if task is None:
                    continue
                if task.owning_team_ids:
                    for team_id in task.owning_team_ids:
                        approvers.update(self.org.lead_user_ids_for_team(team_id))
                else:
                    approvers.update(self.org.lead_user_ids_for_project(task.project_id))
        return approvers

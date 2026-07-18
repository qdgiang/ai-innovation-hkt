"""Owner: A. Read/write port — the ONLY way other modules touch org data
(architecture.md: "org is the one shared *data* port").

STUB — P0 deliverable. Fill in against plan.md P0 ("org v0 + seed loader").
Consumers: decisions (authority lookups), ingestion (provisional-user creation,
G44), signals (party alias matching), surfacing.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from evermind.org.models import Party, Project, Team, User


class OrgService:
    def __init__(self, session: Session):
        self.session = session

    def get_user(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_project(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)

    def get_team(self, team_id: int) -> Team | None:
        return self.session.get(Team, team_id)

    def rank_of(self, user_id: int) -> int:
        """TODO(A): rank snapshot for DEC-4 authority gate."""
        raise NotImplementedError

    def manager_chain(self, user_id: int) -> list[int]:
        """TODO(A): for can_decide's task-scoped manager-chain check."""
        raise NotImplementedError

    def match_party_alias(self, text: str) -> Party | None:
        """TODO(A): fuzzy alias match for SIG-2 waiting_on resolution; confirm on first use."""
        raise NotImplementedError

    def create_provisional_user(self, *, name: str, platform: str,
                                 connector_scope: str, platform_user_id: str) -> User:
        """TODO(A): G44 — called by ingestion's arrival lane. Rejoins reuse the known id."""
        raise NotImplementedError

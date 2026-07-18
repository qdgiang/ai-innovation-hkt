"""Owner: A. Read/write port — the ONLY way other modules touch org data
(architecture.md: "org is the one shared *data* port").

STUB — P0 deliverable. Fill in against plan.md P0 ("org v0 + seed loader").
Consumers: decisions (authority lookups), ingestion (provisional-user creation,
G44), signals (party alias matching), surfacing.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import UserStatus
from evermind.org.models import Party, Project, Team, User, UserTeam


class OrgService:
    def __init__(self, session: Session):
        self.session = session

    def get_user(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_project(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)

    def get_team(self, team_id: int) -> Team | None:
        return self.session.get(Team, team_id)

    def user_for_persona(self, persona: str) -> User | None:
        if persona.isdecimal():
            return self.get_user(int(persona))
        return self.session.scalar(
            select(User).where(User.handle == persona).order_by(User.id).limit(1)
        )

    def rank_of(self, user_id: int) -> int:
        """Return the authority rank, treating an unknown user as unauthorized."""
        user = self.get_user(user_id)
        return (
            user.role_rank
            if user is not None and user.status is not UserStatus.DEPARTED
            else 0
        )

    def manager_chain(self, user_id: int) -> list[int]:
        """Return nearest-to-farthest managers without looping on malformed data."""
        user = self.get_user(user_id)
        if user is None or user.status is UserStatus.DEPARTED:
            return []

        chain: list[int] = []
        seen = {user_id}
        manager_id = user.manager_id
        while manager_id is not None and manager_id not in seen:
            manager = self.get_user(manager_id)
            if manager is None:
                break
            if manager.status is not UserStatus.DEPARTED:
                chain.append(manager.id)
            seen.add(manager.id)
            manager_id = manager.manager_id
        return chain

    def team_ids_for_user(self, user_id: int) -> set[int]:
        return set(
            self.session.scalars(
                select(UserTeam.team_id).where(UserTeam.user_id == user_id)
            )
        )

    def lead_user_ids_for_team(self, team_id: int) -> set[int]:
        return set(
            self.session.scalars(
                select(UserTeam.user_id)
                .join(User, User.id == UserTeam.user_id)
                .where(
                    UserTeam.team_id == team_id,
                    UserTeam.role_in_team == "lead",
                    User.role_rank >= 2,
                    User.status != UserStatus.DEPARTED,
                )
            )
        )

    def lead_user_ids_for_project(self, project_id: int) -> set[int]:
        return set(
            self.session.scalars(
                select(UserTeam.user_id)
                .join(User, User.id == UserTeam.user_id)
                .join(Team, Team.id == UserTeam.team_id)
                .where(
                    Team.project_id == project_id,
                    UserTeam.role_in_team == "lead",
                    User.role_rank >= 2,
                    User.status != UserStatus.DEPARTED,
                )
            )
        )

    def coordinator_user_ids(self) -> set[int]:
        return set(
            self.session.scalars(
                select(User.id).where(
                    User.role_rank >= 3,
                    User.status != UserStatus.DEPARTED,
                )
            )
        )

    def match_party_alias(self, text: str) -> Party | None:
        """TODO(A): fuzzy alias match for SIG-2 waiting_on resolution; confirm on first use."""
        raise NotImplementedError

    def create_provisional_user(self, *, name: str, platform: str,
                                 connector_scope: str, platform_user_id: str) -> User:
        """TODO(A): G44 — called by ingestion's arrival lane. Rejoins reuse the known id."""
        raise NotImplementedError

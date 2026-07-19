"""Owner: A. Read/write port — the ONLY way other modules touch org data
(architecture.md: "org is the one shared *data* port").

Consumers: `decisions` (authority lookups), `ingestion` (provisional-user
creation, G44), `signals` (party alias matching), `surfacing` (recipients),
`api` (/personas). No authority logic lives here — that is `decisions` (DEC-4);
this module only answers *facts* about the org graph.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import UserStatus
from evermind.org.models import (
    ChatGroup, ConfigOp, Party, Project, Team, User, UserIdentity, UserTeam,
)


def _utcnow() -> datetime:
    """Storage stays UTC (G54); columns are tz-naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OrgService:
    def __init__(self, session: Session):
        self.session = session

    # ── reads ────────────────────────────────────────────────────────────

    def get_user(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_user_by_handle(self, handle: str) -> User | None:
        return self.session.scalar(select(User).where(User.handle == handle))

    def get_project(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)

    def get_team(self, team_id: int) -> Team | None:
        return self.session.get(Team, team_id)

    def get_group(self, group_id: int) -> ChatGroup | None:
        return self.session.get(ChatGroup, group_id)

    def get_party(self, party_id: int) -> Party | None:
        return self.session.get(Party, party_id)

    def list_personas(self) -> list[User]:
        """DSH-1 switcher: every seeded user except `departed` (design-v2 §Users)."""
        return list(
            self.session.scalars(
                select(User).where(User.status != UserStatus.DEPARTED).order_by(User.id)
            )
        )

    def rank_of(self, user_id: int) -> int:
        """Rank snapshot source for DEC-4's gate (G10). Unknown user => rank 0
        (can never pass any gate) so `can_decide` stays total (G48)."""
        user = self.get_user(user_id)
        return user.role_rank if user else 0

    def manager_chain(self, user_id: int) -> list[int]:
        """Ancestors bottom-up: [manager, manager's manager, …]. Cycle-safe."""
        chain: list[int] = []
        seen = {user_id}
        current = self.get_user(user_id)
        while current is not None and current.manager_id is not None:
            if current.manager_id in seen:
                break
            chain.append(current.manager_id)
            seen.add(current.manager_id)
            current = self.get_user(current.manager_id)
        return chain

    def is_ancestor(self, ancestor_id: int, user_id: int) -> bool:
        return ancestor_id in self.manager_chain(user_id)

    def teams_of_user(self, user_id: int) -> list[int]:
        return list(
            self.session.scalars(
                select(UserTeam.team_id).where(UserTeam.user_id == user_id)
            )
        )

    def project_ids_of_user(self, user_id: int) -> list[int]:
        """Projects the user belongs to via ANY team membership (G36 matrix).
        Roles are per-team, so the same person naturally scopes differently
        per project — the phân-quyền spec's core premise."""
        rows = self.session.execute(
            select(Team.project_id)
            .join(UserTeam, UserTeam.team_id == Team.id)
            .where(UserTeam.user_id == user_id)
            .distinct()
        )
        return [project_id for (project_id,) in rows]

    def can_view_project(self, user_id: int, project_id: int) -> bool:
        """Spec 'View theo project': membership in any of the project's teams
        grants view; the coordinator (rank 3) sees every project."""
        user = self.get_user(user_id)
        if user is not None and user.role_rank >= 3:
            return True
        return project_id in self.project_ids_of_user(user_id)

    def members_of_team(self, team_id: int) -> list[int]:
        return list(
            self.session.scalars(
                select(UserTeam.user_id).where(UserTeam.team_id == team_id)
            )
        )

    def lead_of_team(self, team_id: int) -> int | None:
        """The `role_in_team == "lead"` row (seed convention, G36)."""
        return self.session.scalar(
            select(UserTeam.user_id).where(
                UserTeam.team_id == team_id, UserTeam.role_in_team == "lead"
            )
        )

    def leads_of_project(self, project_id: int) -> list[int]:
        """Every team lead of the project's teams (G48 project-level governance)."""
        team_ids = list(
            self.session.scalars(select(Team.id).where(Team.project_id == project_id))
        )
        leads: list[int] = []
        for team_id in team_ids:
            lead = self.lead_of_team(team_id)
            if lead is not None and lead not in leads:
                leads.append(lead)
        return leads

    def coordinator(self) -> User | None:
        """The root (linh in the seed): rank 3. Rootless orgs return None —
        DEC-4's rootless fallback handles that (G37)."""
        return self.session.scalar(select(User).where(User.role_rank == 3).order_by(User.id))

    def teams_led_by(self, user_id: int) -> list[int]:
        return list(
            self.session.scalars(
                select(UserTeam.team_id).where(
                    UserTeam.user_id == user_id, UserTeam.role_in_team == "lead"
                )
            )
        )

    def project_of_team(self, team_id: int) -> int | None:
        team = self.get_team(team_id)
        return team.project_id if team else None

    def resolve_identity(
        self, platform: str, connector_scope: str, platform_user_id: str
    ) -> User | None:
        """[D5] the platform-scoped identity key. NEVER matched by display name."""
        identity = self.session.scalar(
            select(UserIdentity).where(
                UserIdentity.platform == platform,
                UserIdentity.connector_scope == connector_scope,
                UserIdentity.platform_user_id == platform_user_id,
            )
        )
        return self.get_user(identity.user_id) if identity else None

    def match_party_alias(self, text: str) -> Party | None:
        """SIG-2 waiting_on resolution: case-insensitive name/alias containment.
        First-use confirmation is the caller's flow; this only matches."""
        needle = text.strip().lower()
        if not needle:
            return None
        for party in self.session.scalars(select(Party)):
            names = [party.name, *(party.aliases or [])]
            for name in names:
                lowered = name.lower()
                if lowered == needle or lowered in needle or needle in lowered:
                    return party
        return None

    # ── writes (the org write port) ──────────────────────────────────────

    def record_config_op(self, actor: str, op: str, payload: dict) -> ConfigOp:
        """Org changes are logged operations, not decisions (data-model.md)."""
        config_op = ConfigOp(ts=_utcnow(), actor=actor, op=op, payload=payload)
        self.session.add(config_op)
        self.session.flush()
        return config_op

    def create_provisional_user(
        self,
        *,
        name: str,
        platform: str,
        connector_scope: str,
        platform_user_id: str,
        team_id: int | None = None,
    ) -> User:
        """G44 arrival lane — called by ingestion (ING-6). Rejoins reuse the
        known identity: never a duplicate provisional (G69)."""
        existing = self.resolve_identity(platform, connector_scope, platform_user_id)
        if existing is not None:
            return existing
        user = User(name=name, handle=None, role_rank=1, manager_id=None,
                    status=UserStatus.PROVISIONAL)
        self.session.add(user)
        self.session.flush()
        self.session.add(UserIdentity(
            user_id=user.id, platform=platform,
            connector_scope=connector_scope, platform_user_id=platform_user_id,
        ))
        if team_id is not None:
            self.session.add(UserTeam(user_id=user.id, team_id=team_id, role_in_team="member"))
        self.record_config_op(
            actor="system",
            op="provisional_user_created",
            payload={"user_id": user.id, "platform_user_id": platform_user_id,
                     "team_id": team_id, "name": name},
        )
        return user

    def confirm_membership(self, user_id: int, actor: str) -> User | None:
        """The lead's one-tap confirm card resolution (G44): provisional → active."""
        user = self.get_user(user_id)
        if user is None:
            return None
        if user.status == UserStatus.PROVISIONAL:
            user.status = UserStatus.ACTIVE
            self.record_config_op(actor=actor, op="membership_confirmed",
                                  payload={"user_id": user_id})
        return user

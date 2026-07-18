from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from evermind.org.models import ChatGroup, Party, Project, Team, User, UserIdentity, UserTeam
from evermind.org.seed_ids import (
    GROUP_IDS,
    PARTY_IDS,
    PROJECT_IDS,
    TEAM_IDS,
    USER_IDS,
    validate_seed_keys,
)
from evermind.org.seed_schema import OrgSeed

_SEQUENCE_TABLES = (
    "projects",
    "teams",
    "chat_groups",
    "users",
    "user_identities",
    "parties",
)


@dataclass(frozen=True)
class SeedSummary:
    projects: int
    teams: int
    groups: int
    users: int
    identities: int
    memberships: int
    parties: int


def _advance_sequences(session: Session) -> None:
    for table_name in _SEQUENCE_TABLES:
        session.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                f"(SELECT MAX(id) FROM {table_name}), true)"
            )
        )


def seed_org(session: Session, seed: OrgSeed) -> SeedSummary:
    validate_seed_keys(seed)

    for project in seed.projects:
        session.merge(
            Project(
                id=PROJECT_IDS[project.id],
                name=project.name,
                kind=project.kind,
                end_date=project.end_date,
                status=project.status,
            )
        )

    for team in seed.teams:
        session.merge(
            Team(
                id=TEAM_IDS[team.id],
                project_id=PROJECT_IDS[team.project_id],
                name=team.name,
            )
        )

    for group in seed.chat_groups:
        session.merge(
            ChatGroup(
                id=GROUP_IDS[group.id],
                platform=group.platform,
                platform_chat_id=group.platform_chat_id,
                project_id=PROJECT_IDS[group.project_id],
                team_id=TEAM_IDS[group.team_id] if group.team_id is not None else None,
            )
        )

    for user in seed.users:
        session.merge(
            User(
                id=USER_IDS[user.handle],
                name=user.name,
                handle=user.handle,
                role_rank=user.role_rank,
                manager_id=None,
                status=user.status,
                departed_at=None,
            )
        )
    session.flush()

    for user in seed.users:
        session.merge(
            User(
                id=USER_IDS[user.handle],
                name=user.name,
                handle=user.handle,
                role_rank=user.role_rank,
                manager_id=USER_IDS[user.manager] if user.manager is not None else None,
                status=user.status,
                departed_at=None,
            )
        )
        session.merge(
            UserIdentity(
                id=USER_IDS[user.handle],
                user_id=USER_IDS[user.handle],
                platform="generic-chat",
                connector_scope="data-v2",
                platform_user_id=user.platform_user_id,
            )
        )

    for membership in seed.user_teams:
        session.merge(
            UserTeam(
                user_id=USER_IDS[membership.user],
                team_id=TEAM_IDS[membership.team],
                role_in_team=membership.role_in_team,
            )
        )

    for party in seed.parties:
        session.merge(
            Party(
                id=PARTY_IDS[party.id],
                name=party.name,
                aliases=list(party.aliases),
                kind=party.kind,
                contact_note=party.contact_note,
            )
        )

    session.flush()
    _advance_sequences(session)
    return SeedSummary(
        projects=len(seed.projects),
        teams=len(seed.teams),
        groups=len(seed.chat_groups),
        users=len(seed.users),
        identities=len(seed.users),
        memberships=len(seed.user_teams),
        parties=len(seed.parties),
    )

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from evermind.contracts.enums import PartyKind, ProjectKind, ProjectStatus, UserStatus


class _StrictSeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SeedMeta(_StrictSeedModel):
    purpose: str
    note: str
    authored: date


class ProjectSeed(_StrictSeedModel):
    id: str
    name: str
    kind: ProjectKind
    end_date: date | None
    status: ProjectStatus


class TeamSeed(_StrictSeedModel):
    id: str
    project_id: str
    name: str


class ChatGroupSeed(_StrictSeedModel):
    id: str
    platform: str
    platform_chat_id: str
    project_id: str
    team_id: str | None
    channel_name: str


class UserSeed(_StrictSeedModel):
    handle: str
    name: str
    role_rank: int
    manager: str | None
    platform_user_id: str
    status: UserStatus


class UserTeamSeed(_StrictSeedModel):
    user: str
    team: str
    role_in_team: str


class PartySeed(_StrictSeedModel):
    id: str
    name: str
    aliases: list[str]
    kind: PartyKind
    contact_note: str | None


class OrgSeed(_StrictSeedModel):
    meta: SeedMeta
    projects: list[ProjectSeed]
    teams: list[TeamSeed]
    chat_groups: list[ChatGroupSeed]
    role_rank_map: dict[str, int]
    users: list[UserSeed]
    user_teams: list[UserTeamSeed]
    parties: list[PartySeed]


def load_org_seed(path: Path) -> OrgSeed:
    return OrgSeed.model_validate_json(path.read_text(encoding="utf-8"))

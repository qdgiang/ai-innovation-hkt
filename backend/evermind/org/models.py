"""Owner: A. Tables: projects, teams, chat_groups, users, user_identities,
user_teams, parties, config_ops (data-model.md §Org & identity).

`decisions` (A, read-only), `signals`/`surfacing` (B) read this module ONLY
through `org.service` — never these tables directly (architecture.md import rule).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from evermind.contracts.enums import PartyKind, ProjectKind, ProjectStatus, UserStatus
from evermind.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    kind: Mapped[ProjectKind]  # [D4] explicit, not inferred from end_date
    end_date: Mapped[datetime | None]
    status: Mapped[ProjectStatus] = mapped_column(default=ProjectStatus.ACTIVE)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str]


class ChatGroup(Base):
    __tablename__ = "chat_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str]
    platform_chat_id: Mapped[str]
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    # set once, PERMANENT (settled #13b; EVM-009: never remapped; new season = new group)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))  # null = project-wide


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    handle: Mapped[str | None]
    role_rank: Mapped[int]  # 3=coordinator 2=lead 1=member (seed map)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[UserStatus] = mapped_column(default=UserStatus.ACTIVE)
    departed_at: Mapped[datetime | None]


class UserIdentity(Base):
    """[D5] identity key is platform-scoped; one internal user <-> many identities;
    NEVER merged by display name."""

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("platform", "connector_scope", "platform_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    platform: Mapped[str]
    connector_scope: Mapped[str]
    platform_user_id: Mapped[str]


class UserTeam(Base):
    """Matrix membership (G36)."""

    __tablename__ = "user_teams"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    role_in_team: Mapped[str | None]


class Party(Base):
    """G32 — externals: vendors, the ward office, a departed treasurer."""

    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    kind: Mapped[PartyKind]
    contact_note: Mapped[str | None]


class ConfigOp(Base):
    """Org changes are logged operations, not decisions."""

    __tablename__ = "config_ops"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime]
    actor: Mapped[str]
    op: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

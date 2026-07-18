"""OPS-1 org seed loader: `data-v2/org.json` → org tables. Owner: A (P0).

Idempotent by natural keys — running it twice updates in place, never
duplicates: projects/parties by name, teams by (project, name), groups by
(platform, platform_chat_id), users by handle. The seed's string ids ("P-TT",
"TEAM-EV", …) are file-local; the DB uses integer PKs and natural keys.

Run: `python -m evermind.org.seed ../data-v2/org.json` (the Makefile `seed`).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import PartyKind, ProjectKind, ProjectStatus, UserStatus
from evermind.org.models import ChatGroup, Party, Project, Team, User, UserIdentity, UserTeam
from evermind.org.service import OrgService

# The single-bot demo constant: [D5] identity keys are (platform, scope, platform_user_id);
# with one bot the scope never varies.
CONNECTOR_SCOPE = "default"


def _parse_date(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def load_org_seed(session: Session, path: str | Path) -> dict[str, dict[str, int]]:
    """Load (or refresh) the org seed. Returns slug→db-id maps per entity kind
    so callers (tests, replay wiring) can resolve the file's local ids."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    project_ids: dict[str, int] = {}
    for row in data.get("projects", []):
        project = session.scalar(select(Project).where(Project.name == row["name"]))
        if project is None:
            project = Project(name=row["name"], kind=ProjectKind(row["kind"]))
            session.add(project)
        project.kind = ProjectKind(row["kind"])
        project.end_date = _parse_date(row.get("end_date"))
        project.status = ProjectStatus(row.get("status", "active"))
        session.flush()
        project_ids[row["id"]] = project.id

    team_ids: dict[str, int] = {}
    for row in data.get("teams", []):
        project_id = project_ids[row["project_id"]]
        team = session.scalar(
            select(Team).where(Team.project_id == project_id, Team.name == row["name"])
        )
        if team is None:
            team = Team(project_id=project_id, name=row["name"])
            session.add(team)
            session.flush()
        team_ids[row["id"]] = team.id

    group_ids: dict[str, int] = {}
    for row in data.get("chat_groups", []):
        if str(row.get("platform_chat_id", "")).startswith("FILL_ME"):
            # runbook placeholder (live telegram group) — seeding it would leave
            # an orphan group row behind once the real chat id replaces it
            continue
        group = session.scalar(
            select(ChatGroup).where(
                ChatGroup.platform == row["platform"],
                ChatGroup.platform_chat_id == row["platform_chat_id"],
            )
        )
        if group is None:
            # project_id is set ONCE here and never remapped (settled #13b, EVM-009)
            group = ChatGroup(
                platform=row["platform"],
                platform_chat_id=row["platform_chat_id"],
                project_id=project_ids[row["project_id"]],
                team_id=team_ids.get(row["team_id"]) if row.get("team_id") else None,
            )
            session.add(group)
            session.flush()
        group_ids[row["id"]] = group.id

    user_ids: dict[str, int] = {}
    for row in data.get("users", []):
        user = session.scalar(select(User).where(User.handle == row["handle"]))
        if user is None:
            user = User(handle=row["handle"], name=row["name"], role_rank=row["role_rank"])
            session.add(user)
        user.name = row["name"]
        user.role_rank = row["role_rank"]
        user.status = UserStatus(row.get("status", "active"))
        session.flush()
        user_ids[row["handle"]] = user.id

    # manager chain — second pass, once every user id exists
    for row in data.get("users", []):
        if row.get("manager"):
            user = session.get(User, user_ids[row["handle"]])
            if user is not None:
                user.manager_id = user_ids[row["manager"]]

    # platform identities [D5]. Two seed shapes:
    # - legacy `platform_user_id` (one key, platform inferred from the first
    #   chat_group — the original single-platform assumption, kept for compat)
    # - explicit `identities: [{platform, platform_user_id[, connector_scope]}]`
    #   so one user can exist on several platforms at once (seeded corpus on
    #   generic-chat + live telegram capture). "FILL_ME"/empty values are
    #   skipped: unfilled runbook placeholders must not become real keys.
    default_platform = data.get("chat_groups", [{}])[0].get("platform", "generic-chat")
    for row in data.get("users", []):
        identities = list(row.get("identities", []))
        if row.get("platform_user_id"):
            identities.append({"platform": default_platform,
                               "platform_user_id": row["platform_user_id"]})
        for identity in identities:
            key = identity.get("platform_user_id", "")
            if not key or key.startswith("FILL_ME"):
                continue
            scope = identity.get("connector_scope", CONNECTOR_SCOPE)
            exists = session.scalar(
                select(UserIdentity).where(
                    UserIdentity.platform == identity["platform"],
                    UserIdentity.connector_scope == scope,
                    UserIdentity.platform_user_id == key,
                )
            )
            if exists is None:
                session.add(UserIdentity(
                    user_id=user_ids[row["handle"]], platform=identity["platform"],
                    connector_scope=scope, platform_user_id=key,
                ))

    for row in data.get("user_teams", []):
        user_id = user_ids[row["user"]]
        team_id = team_ids[row["team"]]
        membership = session.get(UserTeam, (user_id, team_id))
        if membership is None:
            session.add(UserTeam(user_id=user_id, team_id=team_id,
                                 role_in_team=row.get("role_in_team")))
        else:
            membership.role_in_team = row.get("role_in_team")

    party_ids: dict[str, int] = {}
    for row in data.get("parties", []):
        party = session.scalar(select(Party).where(Party.name == row["name"]))
        if party is None:
            party = Party(name=row["name"], kind=PartyKind(row["kind"]))
            session.add(party)
        party.aliases = row.get("aliases", [])
        party.kind = PartyKind(row["kind"])
        party.contact_note = row.get("contact_note")
        session.flush()
        party_ids[row["id"]] = party.id

    OrgService(session).record_config_op(
        actor="seed", op="org_seed_loaded",
        payload={"path": str(path),
                 "counts": {"projects": len(project_ids), "teams": len(team_ids),
                            "groups": len(group_ids), "users": len(user_ids),
                            "parties": len(party_ids)}},
    )
    session.commit()
    return {"projects": project_ids, "teams": team_ids, "groups": group_ids,
            "users": user_ids, "parties": party_ids}


def main() -> None:
    from evermind.db.session import SessionLocal

    path = sys.argv[1] if len(sys.argv) > 1 else "../data-v2/org.json"
    with SessionLocal() as session:
        mapping = load_org_seed(session, path)
    counts = {kind: len(ids) for kind, ids in mapping.items()}
    print(f"org seed loaded from {path}: {counts}")


if __name__ == "__main__":
    main()

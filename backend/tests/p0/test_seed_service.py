from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.contracts.enums import ProjectKind, ProjectStatus
from evermind.org.models import Project, User, UserIdentity, UserTeam
from evermind.org.seed_ids import PROJECT_IDS, TEAM_IDS, USER_IDS
from evermind.org.seed_schema import load_org_seed
from evermind.org.seed_service import seed_org

ORG_FIXTURE = Path(__file__).resolve().parents[3] / "data-v2" / "org.json"


def test_seed_is_idempotent_and_keeps_stable_relationships(db_session: Session):
    seed = load_org_seed(ORG_FIXTURE)
    first = seed_org(db_session, seed)
    second = seed_org(db_session, seed)
    db_session.flush()

    assert first == second
    assert first.projects == 2
    assert first.teams == 2
    assert first.groups == 2
    assert first.users == 9
    assert first.identities == 9
    assert first.memberships == 11
    assert first.parties == 5

    linh = db_session.get(User, USER_IDS["linh"])
    mai = db_session.get(User, USER_IDS["mai"])
    thao = db_session.get(User, USER_IDS["thao"])
    assert linh is not None
    assert mai is not None
    assert thao is not None
    assert mai.manager_id == linh.id
    assert thao.manager_id == mai.id

    khoa_teams = set(
        db_session.scalars(
            select(UserTeam.team_id).where(UserTeam.user_id == USER_IDS["khoa"])
        )
    )
    thao_teams = set(
        db_session.scalars(
            select(UserTeam.team_id).where(UserTeam.user_id == USER_IDS["thao"])
        )
    )
    assert khoa_teams == {TEAM_IDS["TEAM-EV"], TEAM_IDS["TEAM-ED"]}
    assert thao_teams == {TEAM_IDS["TEAM-EV"], TEAM_IDS["TEAM-ED"]}

    linh_identity = db_session.get(UserIdentity, USER_IDS["linh"])
    assert linh_identity is not None
    assert linh_identity.platform == "generic-chat"
    assert linh_identity.connector_scope == "data-v2"

    trung_thu = db_session.get(Project, PROJECT_IDS["P-TT"])
    assert trung_thu is not None
    assert trung_thu.end_date == date(2026, 9, 26)
    assert db_session.scalar(select(User).where(User.handle == "trang")) is None


def test_seed_never_deletes_an_unrelated_project(db_session: Session):
    unrelated = Project(
        id=999,
        name="Unrelated project",
        kind=ProjectKind.PROGRAM,
        end_date=None,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(unrelated)
    db_session.flush()

    seed_org(db_session, load_org_seed(ORG_FIXTURE))

    assert db_session.get(Project, 999) is not None


def test_seed_advances_surrogate_id_sequences(db_session: Session):
    seed_org(db_session, load_org_seed(ORG_FIXTURE))
    project = Project(
        name="Created after seed",
        kind=ProjectKind.PROGRAM,
        end_date=None,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(project)
    db_session.flush()
    assert project.id > max(PROJECT_IDS.values())

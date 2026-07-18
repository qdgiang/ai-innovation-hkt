# Implementer A P0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish A's P0 foundation on top of the merged scaffold with a safe corrective
migration and a deterministic, transactional, idempotent `data-v2` org seed.

**Architecture:** Preserve merged migration `0001` and add a narrow `0002` that fixes
date-only project semantics and completes the decision append-only trigger. Parse the seed
through strict Pydantic models, resolve fixture string keys through explicit integer maps,
and persist seed-owned rows through one SQLAlchemy transaction without deleting unrelated
data.

**Tech Stack:** Python 3.12+ · Pydantic 2 · SQLAlchemy 2 · Alembic · PostgreSQL 16 · pytest
· uv · Docker

## Global Constraints

- Read `ai-docs/implementation/implementer-a-charter.md` and
  `ai-docs/implementation/implementer-a-master-plan.md` completely before editing.
- Start from `feat/a-p0-foundation`, created from the current
  `feature/implementer-a` integration branch.
- Do not modify migration `0001` or any B-owned module.
- Do not implement future-phase `OrgService` authority, party matching, or provisional-user
  behavior in P0.
- Use the fixed seed IDs in this plan; fail on an unknown fixture key.
- Do not reset, drop, or reuse an existing developer database. Migration commands in this
  plan target the disposable container named `evermind-a-p0-db` only.
- Do not delete a file. The approved cleanup of `frontend/next-env.d.ts` is already complete.
- Every behavior follows RED, verify RED, GREEN, verify GREEN, and focused commit.
- Keep every commit below 700 changed lines.
- Unless a step explicitly says otherwise, run its command from the repository root. Every
  database command block sets `DATABASE_URL` itself; do not rely on shell state from a prior
  block.

---

### Task 1: Install and verify the P0 toolchain

**Files:** None.

**Interfaces:**
- Consumes: `backend/pyproject.toml`, `backend/uv.lock`.
- Produces: a locked local Python environment capable of running the repository gates.

- [ ] **Step 1: Confirm the worktree and tool state**

Run from the repository root:

```bash
git status --short --branch
command -v uv || true
python3 --version
docker --version
```

Expected before installation: clean `feat/a-p0-foundation`; no `uv` path; Python 3.12 or
newer; Docker available.

- [ ] **Step 2: Install uv using the already-installed Homebrew**

```bash
brew install uv
uv --version
```

Expected: Homebrew succeeds and `uv --version` prints an installed version without changing
repository files.

- [ ] **Step 3: Sync exactly the locked backend environment**

```bash
(cd backend && uv sync --locked --all-extras --dev)
```

Expected: dependencies install from `uv.lock`; `backend/uv.lock` remains unchanged.

- [ ] **Step 4: Run the existing baseline checks**

```bash
(cd backend && uv run pytest -q tests/test_fixtures_l0.py)
(cd backend && uv run ruff check .)
(cd backend && uv run lint-imports)
git diff --exit-code -- backend/uv.lock
```

Expected: seven L0 tests pass; Ruff and import-linter pass; the lockfile has no diff. If the
merged baseline fails, preserve the exact output and classify it before writing P0 code.

---

### Task 2: Correct date-only project storage and append-only enforcement

**Files:**
- Create: `backend/tests/p0/__init__.py`
- Create: `backend/tests/p0/conftest.py`
- Create: `backend/tests/p0/test_migration_foundation.py`
- Create: `backend/migrations/versions/0002_p0_foundation_corrections.py`
- Modify: `backend/evermind/org/models.py`

**Interfaces:**
- Consumes: migrated `projects` and `decisions` tables from revision `0001`.
- Produces: Alembic revision `0002`; `Project.end_date: date | None`; a null-safe trigger
  that rejects all immutable decision-body changes while allowing lifecycle fields.

- [ ] **Step 1: Start the explicitly disposable PostgreSQL container**

```bash
docker run --detach --rm \
  --name evermind-a-p0-db \
  --env POSTGRES_USER=evermind \
  --env POSTGRES_PASSWORD=evermind \
  --env POSTGRES_DB=evermind \
  --publish 55432:5432 \
  pgvector/pgvector:pg16
until docker exec evermind-a-p0-db pg_isready -U evermind -d evermind; do sleep 1; done
export DATABASE_URL='postgresql+psycopg://evermind:evermind@localhost:55432/evermind'
(cd backend && uv run alembic upgrade 0001)
```

Expected: the named disposable container is healthy and Alembic reports revision `0001`.

- [ ] **Step 2: Add the shared PostgreSQL session fixture**

Create `backend/tests/p0/conftest.py`:

```python
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> Iterator[Session]:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
```

Create an empty `backend/tests/p0/__init__.py` so the P0 test package is explicit.

- [ ] **Step 3: Write failing migration behavior tests**

Create `backend/tests/p0/test_migration_foundation.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from evermind.contracts.enums import CreatedFrom, DecisionScope, DecisionStatus
from evermind.decisions.models import Decision


def _decision(decision_id: int) -> Decision:
    now = datetime.now(UTC)
    return Decision(
        id=decision_id,
        ts=now,
        recorded_at=now,
        decided_by_user_id=1,
        decided_by_role_at_time=3,
        scope=DecisionScope.PROJECT,
        scope_target="project:1",
        description="Keep the approved venue",
        context=None,
        note=None,
        ops=[{"target": "project:1", "facet": "attr:venue", "op": "set", "value": "A"}],
        effect_window_from=None,
        effect_window_until=None,
        status=DecisionStatus.EFFECTIVE,
        rejected_reason=None,
        supersedes_decision_id=None,
        superseded_by_decision_id=None,
        approved_by_user_id=None,
        approval_via=None,
        approved_by_role_at_act=None,
        created_from=CreatedFrom.DASHBOARD,
        confidence=None,
        window_id=None,
        stable_event_id=f"p0-{decision_id}",
    )


def test_project_end_date_is_stored_as_date(db_session: Session):
    data_type = db_session.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='projects' AND column_name='end_date'"
        )
    ).scalar_one()
    assert data_type == "date"


def test_decision_context_is_immutable_even_when_old_value_is_null(db_session: Session):
    decision = _decision(99001)
    db_session.add(decision)
    db_session.flush()

    with pytest.raises(DBAPIError, match="append-only"):
        with db_session.begin_nested():
            decision.context = "A body rewrite must fail"
            db_session.flush()


def test_decision_status_remains_mutable(db_session: Session):
    decision = _decision(99002)
    db_session.add(decision)
    db_session.flush()
    decision.status = DecisionStatus.SUPERSEDED
    db_session.flush()
    assert decision.status is DecisionStatus.SUPERSEDED
```

- [ ] **Step 4: Run the focused tests and verify RED**

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://evermind:evermind@localhost:55432/evermind'
uv run pytest -q tests/p0/test_migration_foundation.py
```

Expected: the date-type assertion fails because `0001` created a timestamp, and the context
immutability assertion fails because the `0001` trigger omits `context` and uses null-unsafe
comparisons.

- [ ] **Step 5: Change the A-owned model to a date-only field**

In `backend/evermind/org/models.py`, import `date` alongside `datetime` and change only this
annotation:

```python
end_date: Mapped[date | None]
```

- [ ] **Step 6: Add the corrective migration**

Create `backend/migrations/versions/0002_p0_foundation_corrections.py`:

```python
"""P0 foundation corrections.

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_TRIGGER = """
CREATE TRIGGER decisions_append_only
BEFORE UPDATE ON decisions
FOR EACH ROW EXECUTE FUNCTION evermind_decisions_append_only();
"""

_CORRECTED_FUNCTION = """
CREATE OR REPLACE FUNCTION evermind_decisions_append_only() RETURNS trigger AS $$
BEGIN
    IF NEW.ts IS DISTINCT FROM OLD.ts
       OR NEW.decided_by_user_id IS DISTINCT FROM OLD.decided_by_user_id
       OR NEW.decided_by_role_at_time IS DISTINCT FROM OLD.decided_by_role_at_time
       OR NEW.scope IS DISTINCT FROM OLD.scope
       OR NEW.scope_target IS DISTINCT FROM OLD.scope_target
       OR NEW.description IS DISTINCT FROM OLD.description
       OR NEW.context IS DISTINCT FROM OLD.context
       OR NEW.ops::text IS DISTINCT FROM OLD.ops::text
       OR NEW.effect_window_from IS DISTINCT FROM OLD.effect_window_from
       OR NEW.effect_window_until IS DISTINCT FROM OLD.effect_window_until
       OR NEW.created_from IS DISTINCT FROM OLD.created_from
       OR NEW.confidence IS DISTINCT FROM OLD.confidence THEN
        RAISE EXCEPTION 'decisions body columns are append-only (settled #2)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_REVISION_0001_FUNCTION = """
CREATE OR REPLACE FUNCTION evermind_decisions_append_only() RETURNS trigger AS $$
BEGIN
    IF NEW.ts <> OLD.ts OR NEW.decided_by_user_id <> OLD.decided_by_user_id
       OR NEW.scope <> OLD.scope OR NEW.scope_target <> OLD.scope_target
       OR NEW.description <> OLD.description OR NEW.ops::text <> OLD.ops::text
       OR NEW.created_from <> OLD.created_from THEN
        RAISE EXCEPTION 'decisions body columns are append-only (settled #2)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def _replace_append_only_trigger(function_sql: str) -> None:
    op.execute("DROP TRIGGER IF EXISTS decisions_append_only ON decisions")
    op.execute(function_sql)
    op.execute(_TRIGGER)


def upgrade() -> None:
    op.alter_column(
        "projects",
        "end_date",
        existing_type=sa.DateTime(),
        type_=sa.Date(),
        existing_nullable=True,
        postgresql_using="end_date::date",
    )
    _replace_append_only_trigger(_CORRECTED_FUNCTION)


def downgrade() -> None:
    _replace_append_only_trigger(_REVISION_0001_FUNCTION)
    op.alter_column(
        "projects",
        "end_date",
        existing_type=sa.Date(),
        type_=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="end_date::timestamp",
    )
```

The corrected function deliberately excludes lifecycle fields (`status`, rejection,
supersession, and approval fields), which remain mutable. It includes every immutable field
listed by `data-model.md`; `note` remains outside that immutable list. Downgrade restores the
exact revision-`0001` function rather than leaving the prior revision without its trigger.

- [ ] **Step 7: Upgrade and verify GREEN**

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://evermind:evermind@localhost:55432/evermind'
uv run alembic upgrade head
uv run pytest -q tests/p0/test_migration_foundation.py
```

Expected: all three focused tests pass.

- [ ] **Step 8: Verify the supported migration path in both directions**

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://evermind:evermind@localhost:55432/evermind'
uv run alembic downgrade 0001
uv run alembic upgrade head
uv run pytest -q tests/p0/test_migration_foundation.py
```

Expected: downgrade and re-upgrade succeed; all focused tests pass again.

- [ ] **Step 9: Commit the migration behavior**

```bash
cd "$(git rev-parse --show-toplevel)"
git add backend/evermind/org/models.py \
  backend/migrations/versions/0002_p0_foundation_corrections.py \
  backend/tests/p0
git commit -m "fix(db): add corrective P0 migration"
```

Expected: one focused commit below 700 changed lines.

---

### Task 3: Validate the fixture and resolve deterministic IDs

**Files:**
- Create: `backend/evermind/org/seed_schema.py`
- Create: `backend/evermind/org/seed_ids.py`
- Create: `backend/tests/p0/test_seed_contract.py`

**Interfaces:**
- Produces: `load_org_seed(path: Path) -> OrgSeed` and
  `validate_seed_keys(seed: OrgSeed) -> None`.
- Fixed maps: projects `P-TT=1`, `P-CL=2`; teams `TEAM-EV=1`, `TEAM-ED=2`; groups
  `G-TT=1`, `G-CL=2`; parties `PTY-KL=1`, `PTY-ND=2`, `PTY-WD=3`, `PTY-SL=4`,
  `PTY-YEN=5`; users `linh=1`, `mai=2`, `duc=3`, `minh=4`, `huong=5`, `an=6`,
  `khoa=7`, `thao=8`, `tuan=9`.

- [ ] **Step 1: Write fixture-contract tests**

Create `backend/tests/p0/test_seed_contract.py`:

```python
from pathlib import Path

import pytest

from evermind.org.seed_ids import (
    GROUP_IDS,
    PARTY_IDS,
    PROJECT_IDS,
    TEAM_IDS,
    USER_IDS,
    validate_seed_keys,
)
from evermind.org.seed_schema import load_org_seed

ORG_FIXTURE = Path(__file__).resolve().parents[3] / "data-v2" / "org.json"


def test_data_v2_seed_matches_explicit_id_contract():
    seed = load_org_seed(ORG_FIXTURE)
    validate_seed_keys(seed)
    assert PROJECT_IDS == {"P-TT": 1, "P-CL": 2}
    assert TEAM_IDS == {"TEAM-EV": 1, "TEAM-ED": 2}
    assert GROUP_IDS == {"G-TT": 1, "G-CL": 2}
    assert PARTY_IDS == {
        "PTY-KL": 1,
        "PTY-ND": 2,
        "PTY-WD": 3,
        "PTY-SL": 4,
        "PTY-YEN": 5,
    }
    assert USER_IDS == {
        "linh": 1,
        "mai": 2,
        "duc": 3,
        "minh": 4,
        "huong": 5,
        "an": 6,
        "khoa": 7,
        "thao": 8,
        "tuan": 9,
    }
    assert len(seed.users) == 9
    assert all(user.handle != "trang" for user in seed.users)


def test_unknown_project_key_fails_instead_of_being_guessed():
    seed = load_org_seed(ORG_FIXTURE)
    unknown = seed.model_copy(
        update={"projects": [*seed.projects, seed.projects[0].model_copy(update={"id": "P-X"})]}
    )
    with pytest.raises(ValueError, match="unknown project fixture keys: P-X"):
        validate_seed_keys(unknown)
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
(cd backend && uv run pytest -q tests/p0/test_seed_contract.py)
```

Expected: collection fails because `seed_schema` and `seed_ids` do not exist.

- [ ] **Step 3: Implement strict Pydantic seed models**

Create `backend/evermind/org/seed_schema.py`:

```python
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
```

- [ ] **Step 4: Implement explicit maps and cross-reference validation**

Create `backend/evermind/org/seed_ids.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from evermind.org.seed_schema import OrgSeed

PROJECT_IDS = {"P-TT": 1, "P-CL": 2}
TEAM_IDS = {"TEAM-EV": 1, "TEAM-ED": 2}
GROUP_IDS = {"G-TT": 1, "G-CL": 2}
PARTY_IDS = {"PTY-KL": 1, "PTY-ND": 2, "PTY-WD": 3, "PTY-SL": 4, "PTY-YEN": 5}
USER_IDS = {
    "linh": 1,
    "mai": 2,
    "duc": 3,
    "minh": 4,
    "huong": 5,
    "an": 6,
    "khoa": 7,
    "thao": 8,
    "tuan": 9,
}
ROLE_RANK_MAP = {"coordinator": 3, "lead": 2, "member": 1}


def _assert_exact(actual: set[str], expected: dict[str, int], kind: str) -> None:
    unknown = sorted(actual - expected.keys())
    missing = sorted(expected.keys() - actual)
    if unknown:
        raise ValueError(f"unknown {kind} fixture keys: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing {kind} fixture keys: {', '.join(missing)}")


def _assert_references(refs: Iterable[str], valid: set[str], kind: str) -> None:
    missing = sorted(set(refs) - valid)
    if missing:
        raise ValueError(f"unknown {kind} references: {', '.join(missing)}")


def validate_seed_keys(seed: OrgSeed) -> None:
    _assert_exact({row.id for row in seed.projects}, PROJECT_IDS, "project")
    _assert_exact({row.id for row in seed.teams}, TEAM_IDS, "team")
    _assert_exact({row.id for row in seed.chat_groups}, GROUP_IDS, "group")
    _assert_exact({row.id for row in seed.parties}, PARTY_IDS, "party")
    _assert_exact({row.handle for row in seed.users}, USER_IDS, "user")

    if seed.role_rank_map != ROLE_RANK_MAP:
        raise ValueError(f"role_rank_map must equal {ROLE_RANK_MAP!r}")

    project_keys = set(PROJECT_IDS)
    team_keys = set(TEAM_IDS)
    user_keys = set(USER_IDS)
    _assert_references((row.project_id for row in seed.teams), project_keys, "team project")
    _assert_references(
        (row.project_id for row in seed.chat_groups), project_keys, "group project"
    )
    _assert_references(
        (row.team_id for row in seed.chat_groups if row.team_id is not None),
        team_keys,
        "group team",
    )
    _assert_references(
        (row.manager for row in seed.users if row.manager is not None),
        user_keys,
        "manager",
    )
    _assert_references((row.user for row in seed.user_teams), user_keys, "membership user")
    _assert_references((row.team for row in seed.user_teams), team_keys, "membership team")

    platform_ids = [row.platform_user_id for row in seed.users]
    if len(platform_ids) != len(set(platform_ids)):
        raise ValueError("platform_user_id values must be unique")

    memberships = [(row.user, row.team) for row in seed.user_teams]
    if len(memberships) != len(set(memberships)):
        raise ValueError("user-team memberships must be unique")
```

- [ ] **Step 5: Run the focused test and verify GREEN**

```bash
(cd backend && uv run pytest -q tests/p0/test_seed_contract.py)
```

Expected: all fixture-contract tests pass.

- [ ] **Step 6: Commit the validated seed contract**

```bash
cd "$(git rev-parse --show-toplevel)"
git add backend/evermind/org/seed_schema.py \
  backend/evermind/org/seed_ids.py \
  backend/tests/p0/test_seed_contract.py
git commit -m "feat(org): validate deterministic seed identities"
```
---

## P0 continuation

Complete Tasks 4–7 in [`a-p0-foundation-seed-and-gate.md`](a-p0-foundation-seed-and-gate.md)
after Task 3. Both files form the approved P0 phase brief package.

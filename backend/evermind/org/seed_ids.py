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


def _assert_unique(values: Iterable[str], kind: str) -> None:
    items = list(values)
    if len(items) != len(set(items)):
        raise ValueError(f"{kind} must be unique")


def validate_seed_keys(seed: OrgSeed) -> None:
    _assert_unique((row.id for row in seed.projects), "project ids")
    _assert_unique((row.id for row in seed.teams), "team ids")
    _assert_unique((row.id for row in seed.chat_groups), "group ids")
    _assert_unique((row.id for row in seed.parties), "party ids")
    _assert_unique((row.handle for row in seed.users), "user handles")

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

    team_projects = {row.id: row.project_id for row in seed.teams}
    if any(
        row.team_id is not None and team_projects[row.team_id] != row.project_id
        for row in seed.chat_groups
    ):
        raise ValueError("group team must belong to the group project")

    if any(row.role_rank not in {1, 2, 3} for row in seed.users):
        raise ValueError("role ranks must be one of 1, 2, 3")

    managers = {row.handle: row.manager for row in seed.users}
    for handle in managers:
        seen: set[str] = set()
        current: str | None = handle
        while current is not None:
            if current in seen:
                raise ValueError("manager relationships must be acyclic")
            seen.add(current)
            current = managers[current]

    platform_ids = [row.platform_user_id for row in seed.users]
    if len(platform_ids) != len(set(platform_ids)):
        raise ValueError("platform_user_id values must be unique")

    memberships = [(row.user, row.team) for row in seed.user_teams]
    if len(memberships) != len(set(memberships)):
        raise ValueError("user-team memberships must be unique")

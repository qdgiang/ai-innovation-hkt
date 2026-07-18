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


@pytest.mark.parametrize(
    ("collection", "key", "message"),
    [
        ("projects", "id", "project ids must be unique"),
        ("teams", "id", "team ids must be unique"),
        ("chat_groups", "id", "group ids must be unique"),
        ("parties", "id", "party ids must be unique"),
        ("users", "handle", "user handles must be unique"),
    ],
)
def test_duplicate_fixture_keys_are_rejected(collection: str, key: str, message: str):
    seed = load_org_seed(ORG_FIXTURE)
    rows = getattr(seed, collection)
    duplicate = rows[0].model_copy(update={key: getattr(rows[0], key)})
    invalid = seed.model_copy(update={collection: [*rows, duplicate]})

    with pytest.raises(ValueError, match=message):
        validate_seed_keys(invalid)


def test_group_team_must_belong_to_the_group_project():
    seed = load_org_seed(ORG_FIXTURE)
    group = seed.chat_groups[0]
    wrong_team = next(team for team in seed.teams if team.project_id != group.project_id)
    invalid_group = group.model_copy(update={"team_id": wrong_team.id})
    invalid = seed.model_copy(
        update={"chat_groups": [invalid_group, *seed.chat_groups[1:]]}
    )

    with pytest.raises(ValueError, match="group team must belong to the group project"):
        validate_seed_keys(invalid)


@pytest.mark.parametrize("rank", [0, 4])
def test_role_rank_must_be_supported(rank: int):
    seed = load_org_seed(ORG_FIXTURE)
    invalid_user = seed.users[0].model_copy(update={"role_rank": rank})
    invalid = seed.model_copy(update={"users": [invalid_user, *seed.users[1:]]})

    with pytest.raises(ValueError, match="role ranks must be one of 1, 2, 3"):
        validate_seed_keys(invalid)


def test_manager_cycles_are_rejected():
    seed = load_org_seed(ORG_FIXTURE)
    first, second, *remaining = seed.users
    cycle = [
        first.model_copy(update={"manager": second.handle}),
        second.model_copy(update={"manager": first.handle}),
        *remaining,
    ]
    invalid = seed.model_copy(update={"users": cycle})

    with pytest.raises(ValueError, match="manager relationships must be acyclic"):
        validate_seed_keys(invalid)

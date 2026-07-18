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

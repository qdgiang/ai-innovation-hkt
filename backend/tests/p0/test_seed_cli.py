from pathlib import Path

from sqlalchemy.orm import Session

from evermind.org.seed import run_seed

ORG_FIXTURE = Path(__file__).resolve().parents[3] / "data-v2" / "org.json"


def test_run_seed_loads_fixture_and_returns_summary(db_session: Session):
    summary = run_seed(ORG_FIXTURE, db_session)
    assert summary.users == 9
    assert summary.memberships == 11

from pathlib import Path
from contextlib import contextmanager

from sqlalchemy.orm import Session

from evermind.org import seed as seed_cli
from evermind.org.seed import run_seed

ORG_FIXTURE = Path(__file__).resolve().parents[3] / "data-v2" / "org.json"


def test_run_seed_loads_fixture_and_returns_summary(db_session: Session):
    summary = run_seed(ORG_FIXTURE, db_session)
    assert summary.users == 9
    assert summary.memberships == 11


def test_main_uses_one_transaction_and_prints_sorted_summary(
    db_session: Session, monkeypatch, capsys
):
    begins = 0

    @contextmanager
    def begin():
        nonlocal begins
        begins += 1
        yield db_session

    monkeypatch.setattr(seed_cli.SessionLocal, "begin", begin)

    assert seed_cli.main([str(ORG_FIXTURE)]) == 0
    assert begins == 1
    assert capsys.readouterr().out == (
        '{"groups": 2, "identities": 9, "memberships": 11, "parties": 5, '
        '"projects": 2, "teams": 2, "users": 9}\n'
    )

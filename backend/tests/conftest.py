"""Shared L1 fixtures — real Postgres (compose), no LLM, no network
(testing-strategy.md §L1). Each test runs inside a rolled-back transaction so
tests never see each other's data.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from evermind.config import settings

# Import every module's models once so Base.metadata / mappers are fully
# configured before any test constructs a model instance (mirrors
# migrations/env.py's import list).
from evermind.org import models as _org_models  # noqa: F401
from evermind.connectors import models as _connectors_models  # noqa: F401
from evermind.ingestion import models as _ingestion_models  # noqa: F401
from evermind.decisions import models as _decisions_models  # noqa: F401
from evermind.db import eventlog as _eventlog_models  # noqa: F401
from evermind.tasks import models as _tasks_models  # noqa: F401
from evermind.signals import models as _signals_models  # noqa: F401
from evermind.surfacing import models as _surfacing_models  # noqa: F401


@pytest.fixture(scope="session")
def engine():
    return create_engine(settings.database_url)


@pytest.fixture()
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

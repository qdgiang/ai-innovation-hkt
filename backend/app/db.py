"""Engine/session wiring. SQLite in Phase 0-1 dev; Railway Postgres from Phase 2.

For Postgres, infra/schema.sql is the canonical DDL (applied by compose initdb /
Alembic later); `create_all` covers SQLite dev, where the >=1-citation rule is
enforced app-side in repository.save_record.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Session:
    return SessionLocal()


def init_db() -> None:
    from backend.app import models

    models.Base.metadata.create_all(engine)

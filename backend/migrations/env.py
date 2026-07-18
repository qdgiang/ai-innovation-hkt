from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from evermind.config import settings
from evermind.db.base import Base

# Import every module's models so they register on Base.metadata before
# `create_all`/autogenerate runs. New module = one line here (P0 shared file;
# each owner adds their own import when their module's models.py lands).
from evermind.org import models as _org_models  # noqa: F401
from evermind.connectors import models as _connectors_models  # noqa: F401
from evermind.ingestion import models as _ingestion_models  # noqa: F401
from evermind.decisions import models as _decisions_models  # noqa: F401
from evermind.db import eventlog as _eventlog_models  # noqa: F401
from evermind.tasks import models as _tasks_models  # noqa: F401
from evermind.signals import models as _signals_models  # noqa: F401
from evermind.surfacing import models as _surfacing_models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

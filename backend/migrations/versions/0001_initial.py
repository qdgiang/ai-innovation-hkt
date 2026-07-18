"""initial schema — full data-model.md, all modules' tables

Revision ID: 0001
Revises:
Create Date: 2026-07-18

P0 shared deliverable (plan.md): "Alembic migration 0001 = the full data-model
(including plumbing tables)." After this lands, each module owner migrates
their own tables in later revisions (architecture.md).

NOTE: this revision creates tables via `Base.metadata.create_all` (every
module's models.py registers on import in `migrations/env.py`) rather than
hand-written `op.create_table` calls per table — a deliberate speed tradeoff
for the hackathon clock (plan.md P0 is "half a day"). If reviewability/
per-table rollback becomes a real need later, regenerate this file with
`alembic revision --autogenerate` against a running db and replace this body.
"""
from __future__ import annotations

from alembic import op

from evermind.db.base import Base

# Ensure every module's tables are registered on Base.metadata (mirrors the
# import list in migrations/env.py).
from evermind.org import models as _org_models  # noqa: F401
from evermind.connectors import models as _connectors_models  # noqa: F401
from evermind.ingestion import models as _ingestion_models  # noqa: F401
from evermind.decisions import models as _decisions_models  # noqa: F401
from evermind.db import eventlog as _eventlog_models  # noqa: F401
from evermind.tasks import models as _tasks_models  # noqa: F401
from evermind.signals import models as _signals_models  # noqa: F401
from evermind.surfacing import models as _surfacing_models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    # Append-only enforcement (data-model.md invariant #4 / settled #2): a trigger
    # rejecting UPDATEs on decisions' body columns. TODO(A): add before P1 exit —
    # tracked here so it's not forgotten, not because it's hard.
    op.execute(
        """
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
    )
    op.execute(
        """
        CREATE TRIGGER decisions_append_only
        BEFORE UPDATE ON decisions
        FOR EACH ROW EXECUTE FUNCTION evermind_decisions_append_only();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS decisions_append_only ON decisions")
    op.execute("DROP FUNCTION IF EXISTS evermind_decisions_append_only")
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

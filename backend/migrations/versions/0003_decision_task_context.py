"""decisions: task-creation context columns (new_task_id, context_project_id)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-18

Owner: A (`decisions` tables).

PR #46 added two nullable columns to the `decisions` model — stamped at propose
time for NEW_TASK decisions so the APPROVAL path can re-emit the same
new_task_id/project_id the born-effective path does (without them the tasks
consumer materializes approved tasks under the 0-placeholder project, and any
full-model SELECT on an un-migrated DB fails with UndefinedColumn, e.g.
/qa → KnowledgeService.retrieve()).

IF NOT EXISTS because some running DBs already received these columns via a
hand ALTER during the live-verify pass — the migration must converge, not fail.
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE decisions ADD COLUMN IF NOT EXISTS new_task_id integer")
    op.execute(
        "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS context_project_id integer"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE decisions DROP COLUMN IF EXISTS new_task_id")
    op.execute("ALTER TABLE decisions DROP COLUMN IF EXISTS context_project_id")

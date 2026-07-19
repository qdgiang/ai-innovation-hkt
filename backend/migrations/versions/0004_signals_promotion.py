"""signals-promotion pipeline: signal provenance + decision review lane

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19

Combined PR #52 + PR #53 harvest (credit pqminh27 for reporter/evidence/
review_reason shapes). Additive + idempotent (0002's IF NOT EXISTS pattern):
fresh DBs already get these via 0001's create_all over live models.

- signals.reported_by_user_id  — who voiced the mention (promotion proposes
  in the first reporter's name)
- signals.waiting_on_text      — G22 free-text counterparty when unmatched
- signals.evidence             — per-mention [{message_id, rev_at_capture}]
- decisions.review_reason      — WHY a system proposal is held for review
- decisions.reported_by_user_id — whose evidence triggered it
"""
from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE signals ADD COLUMN IF NOT EXISTS reported_by_user_id INTEGER")
    op.execute("ALTER TABLE signals ADD COLUMN IF NOT EXISTS waiting_on_text VARCHAR")
    op.execute("ALTER TABLE signals ADD COLUMN IF NOT EXISTS evidence JSON")
    op.execute("ALTER TABLE decisions ADD COLUMN IF NOT EXISTS review_reason VARCHAR")
    op.execute("ALTER TABLE decisions ADD COLUMN IF NOT EXISTS reported_by_user_id INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE decisions DROP COLUMN IF EXISTS reported_by_user_id")
    op.execute("ALTER TABLE decisions DROP COLUMN IF EXISTS review_reason")
    op.execute("ALTER TABLE signals DROP COLUMN IF EXISTS evidence")
    op.execute("ALTER TABLE signals DROP COLUMN IF EXISTS waiting_on_text")
    op.execute("ALTER TABLE signals DROP COLUMN IF EXISTS reported_by_user_id")

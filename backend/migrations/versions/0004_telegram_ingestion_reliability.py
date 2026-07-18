"""telegram capture provenance and resilient LLM extraction

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19

`0001` creates tables from live ORM metadata, so a fresh database can mask
columns added by later code. This migration is deliberately explicit for
databases already stamped at 0003.
"""
from __future__ import annotations

from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS author_platform_id varchar")
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS captured_at timestamptz")
    op.execute("UPDATE messages SET captured_at = ts WHERE captured_at IS NULL")
    op.execute("ALTER TABLE messages ALTER COLUMN captured_at SET DEFAULT CURRENT_TIMESTAMP")
    op.execute("ALTER TABLE messages ALTER COLUMN captured_at SET NOT NULL")
    op.execute(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS mentions jsonb NOT NULL DEFAULT '[]'::jsonb"
    )

    op.execute("ALTER TABLE reaction_acts ALTER COLUMN user_id TYPE bigint USING user_id::bigint")
    op.execute("ALTER TABLE group_members ALTER COLUMN user_id TYPE bigint USING user_id::bigint")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_identity_aliases (
            id serial PRIMARY KEY,
            user_id integer NOT NULL REFERENCES users(id),
            platform varchar NOT NULL,
            connector_scope varchar NOT NULL,
            username varchar NOT NULL,
            CONSTRAINT uq_user_identity_aliases_scope_username_user
                UNIQUE (platform, connector_scope, username, user_id)
        )
        """
    )

    op.execute("ALTER TABLE ingest_cursors ADD COLUMN IF NOT EXISTS captured_at timestamptz")
    op.execute("ALTER TABLE ingest_cursors ADD COLUMN IF NOT EXISTS message_id integer")
    op.execute("ALTER TABLE extraction_windows ADD COLUMN IF NOT EXISTS error_count integer NOT NULL DEFAULT 0")
    op.execute(
        "ALTER TABLE extraction_windows ADD COLUMN IF NOT EXISTS error_summary jsonb NOT NULL DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE extraction_windows DROP COLUMN IF EXISTS error_summary")
    op.execute("ALTER TABLE extraction_windows DROP COLUMN IF EXISTS error_count")
    op.execute("ALTER TABLE ingest_cursors DROP COLUMN IF EXISTS message_id")
    op.execute("ALTER TABLE ingest_cursors DROP COLUMN IF EXISTS captured_at")
    op.execute("DROP TABLE IF EXISTS user_identity_aliases")
    op.execute("ALTER TABLE group_members ALTER COLUMN user_id TYPE integer USING user_id::integer")
    op.execute("ALTER TABLE reaction_acts ALTER COLUMN user_id TYPE integer USING user_id::integer")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS mentions")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS captured_at")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS author_platform_id")

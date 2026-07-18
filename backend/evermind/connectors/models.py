"""Owner: B. Tables: messages, message_revisions, reaction_acts, group_members
(data-model.md §Messages & acts; architecture.md module table).

Exposes a READ-ONLY service port for `ingestion` (A) — work-split.md interface #1.
Never calls the LLM; never touches domain (decisions/tasks) tables; never sends
anything to any platform (settled #20 — no send capability exists, structurally).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from evermind.contracts.enums import MessageKind
from evermind.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str]  # replay | telegram | transcript
    group_id: Mapped[int | None]
    author_identity: Mapped[str]
    ts: Mapped[datetime]
    text: Mapped[str]  # caption when kind is media
    thread_ref: Mapped[int | None]  # reply target (message id)
    raw_ref: Mapped[str]  # provenance: corpus line / platform update id
    kind: Mapped[MessageKind] = mapped_column(default=MessageKind.TEXT)
    media_ref: Mapped[str | None]
    forward_origin: Mapped[str | None]
    current_rev: Mapped[int] = mapped_column(default=1)
    tombstoned_at: Mapped[datetime | None]  # delete-signal -> tombstone, never hard-delete


class MessageRevision(Base):
    """G45: edits append, never overwrite."""

    __tablename__ = "message_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"))
    rev: Mapped[int]
    text: Mapped[str]
    edited_at: Mapped[datetime]


class ReactionAct(Base):
    """G67: acts, not messages; recorded ONLY on tracked messages (checked via
    `decisions.service.tracked_message_ids` before insert — interface #8).
    """

    __tablename__ = "reaction_acts"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"))
    user_id: Mapped[int]
    emoji: Mapped[str]
    ts: Mapped[datetime]
    removed_at: Mapped[datetime | None]


class GroupMember(Base):
    """G69: room membership from membership events. Leaving a room NEVER changes
    users.status — org departure is only ever an explicit config op.
    """

    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)
    joined_at: Mapped[datetime]
    left_at: Mapped[datetime | None]

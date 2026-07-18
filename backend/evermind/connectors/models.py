"""Owner: B. Tables: messages, message_revisions, reaction_acts, group_members
(data-model.md §Messages & acts; architecture.md module table).

Exposes a READ-ONLY service port for `ingestion` (A) — work-split.md interface #1.
Never calls the LLM; never touches domain (decisions/tasks) tables; never sends
anything to any platform (settled #20 — no send capability exists, structurally).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from evermind.contracts.enums import MessageKind
from evermind.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str]  # replay | telegram | transcript
    group_id: Mapped[int | None]
    author_identity: Mapped[str]
    # [D5] the platform's STABLE numeric user id (as text, platform-agnostic),
    # when the platform provides one. author_identity stays the display-ish
    # handle (telegram: username when set) — usernames are mutable, so identity
    # resolution prefers this column (ingestion/identity.py).
    author_platform_id: Mapped[str | None]
    ts: Mapped[datetime]
    # Capture order is deliberately separate from the platform event time: a
    # delayed Telegram update must not be skipped by a replay cursor.
    captured_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    text: Mapped[str]  # caption when kind is media
    # Compact platform provenance only. Task assignment remains owned by
    # TaskAssignment, never by captured messages.
    mentions: Mapped[list[dict] | None] = mapped_column(default=list)
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
    user_id: Mapped[int] = mapped_column(BigInteger)  # platform id: exceeds int32
    emoji: Mapped[str]
    ts: Mapped[datetime]
    removed_at: Mapped[datetime | None]


class GroupMember(Base):
    """G69: room membership from membership events. Leaving a room NEVER changes
    users.status — org departure is only ever an explicit config op.
    """

    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(primary_key=True)
    # the PLATFORM user id — modern telegram ids (and bot ids) exceed int32
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    joined_at: Mapped[datetime]
    left_at: Mapped[datetime | None]


class Upload(Base):
    """[EVM-011] txt/md only; re-upload = NEW version row, never overwrite.
    CAP-3 (plan.md P3 Lane B) writes this — see ingestion/models.py's note on
    why this table lives here rather than in `ingestion`.
    """

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    mime: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    uploaded_at: Mapped[datetime]
    uploaded_by: Mapped[int]


class SpeakerMap(Base):
    """G30 — per-upload; unmapped speaker => their decisions born proposed."""

    __tablename__ = "speaker_maps"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"))
    display_name: Mapped[str]
    user_id: Mapped[int | None]

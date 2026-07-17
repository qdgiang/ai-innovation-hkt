"""Frozen contracts (ai-docs/features.md — "Key contracts, freeze early").

    Message  {id, source, channel, team?, author, ts, text, thread_ref?, raw_ref}
    Record   {id, type: decision|blocker|status, title, body(json per type),
              team, created_from: marker|llm, confidence, status: active|superseded|rejected}
    Citation {record_id, message_id}   -- every record >=1 citation, enforced

Changes here are contract changes: they need explicit sign-off, not silent drift.

The per-type body payloads carry a `kind` discriminator so validation can route a
plain dict to the right body model; on input `kind` may be omitted and is inferred
from the record's `type`.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Source(StrEnum):
    TELEGRAM = "telegram"
    TRANSCRIPT = "transcript"
    REPLAY = "replay"


class Message(BaseModel):
    """One canonical ingested message; immutable source evidence."""

    model_config = ConfigDict(frozen=True)

    id: str
    source: Source
    channel: str
    team: str | None = None
    author: str
    ts: AwareDatetime
    text: str
    thread_ref: str | None = None
    raw_ref: str


class RecordType(StrEnum):
    DECISION = "decision"
    BLOCKER = "blocker"
    STATUS = "status"


class RecordStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class CreatedFrom(StrEnum):
    MARKER = "marker"
    LLM = "llm"


class DecisionBody(BaseModel):
    kind: Literal["decision"] = "decision"
    summary: str
    rationale: str | None = None
    decided_by: str | None = None
    date: dt.date | None = None
    supersedes: str | None = None  # id of the superseded Record


class BlockerBody(BaseModel):
    kind: Literal["blocker"] = "blocker"
    waiting_on: str
    owner: str | None = None
    since: dt.date | None = None
    resolved: bool = False


class StatusBody(BaseModel):
    kind: Literal["status"] = "status"
    summary: str
    period: str  # ISO week, e.g. "2026-W26"


RecordBody = Annotated[DecisionBody | BlockerBody | StatusBody, Field(discriminator="kind")]


class Record(BaseModel):
    id: str
    type: RecordType
    title: str
    body: RecordBody
    team: str | None = None
    created_from: CreatedFrom
    confidence: float = Field(ge=0.0, le=1.0)
    status: RecordStatus = RecordStatus.ACTIVE

    @model_validator(mode="before")
    @classmethod
    def _infer_body_kind(cls, data: object) -> object:
        if isinstance(data, dict):
            body = data.get("body")
            if isinstance(body, dict) and "kind" not in body and "type" in data:
                data = {**data, "body": {**body, "kind": str(data["type"])}}
        return data

    @model_validator(mode="after")
    def _body_matches_type(self) -> Record:
        if self.body.kind != self.type.value:
            raise ValueError(f"record type {self.type.value!r} has {self.body.kind!r} body")
        return self


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: str
    message_id: str


class ExtractedRecord(BaseModel):
    """AI-layer output: a Record plus the message ids that support it.

    The >=1-citation rule starts at this boundary (min_length=1); the persistence
    layer enforces it again before anything reaches the DB.
    """

    record: Record
    citation_message_ids: list[str] = Field(min_length=1)

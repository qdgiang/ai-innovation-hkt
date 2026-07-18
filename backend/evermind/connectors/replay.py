"""Owner: B. CAP-2 — replay connector: feeds a corpus JSONL file (shape:
data-v2/README.md — one canonical Message per line, `id`/`raw_ref` fields,
globally time-sorted) through the same `messages` table live capture uses.
Instant mode (tests, REPLAY_PACE_MS=0) and paced mode (demo beat: records
materialize on screen one at a time).

`connectors` may not import `org` (architecture.md's allowlist doesn't
include it), so channel -> `chat_groups.id` resolution is the CALLER's job —
the seed/replay CLI (which loads org first) passes the mapping in.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message


def _parse_message_id(raw_id: str) -> int:
    # "m0001" -> 1 (data-v2/README.md: id ALWAYS equals the corpus line number)
    return int(raw_id.lstrip("m"))


class ReplayConnector:
    def __init__(self, session: Session):
        self.session = session

    def replay(self, corpus_path: Path, *, channel_group_ids: dict[str, int],
               pace_ms: int = 0) -> int:
        count = 0
        with open(corpus_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if self._already_ingested(row["raw_ref"]):
                    continue  # idempotent re-run
                self._insert_message(row, channel_group_ids)
                count += 1
                if pace_ms:
                    time.sleep(pace_ms / 1000)
        return count

    def _already_ingested(self, raw_ref: str) -> bool:
        existing = self.session.scalars(
            select(Message).where(Message.raw_ref == raw_ref)
        ).first()
        return existing is not None

    def _insert_message(self, row: dict, channel_group_ids: dict[str, int]) -> None:
        thread_ref = _parse_message_id(row["thread_ref"]) if row.get("thread_ref") else None
        message = Message(
            id=_parse_message_id(row["id"]),
            source=row.get("source", "replay"),
            group_id=channel_group_ids.get(row["channel"]),
            author_identity=row["author"],
            ts=datetime.fromisoformat(row["ts"]),
            text=row["text"],
            thread_ref=thread_ref,
            raw_ref=row["raw_ref"],
            kind=row.get("kind", "text"),
            media_ref=row.get("media_ref"),
            forward_origin=row.get("forward_origin"),
        )
        self.session.add(message)
        self.session.flush()

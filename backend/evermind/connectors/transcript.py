"""Owner: B. CAP-3 — transcript upload connector: `[MM:SS] Name: text` parsing +
attendee header; `.txt`/`.md` only [EVM-011]. Speaker map auto-seeded from the
turns' display names, confirmable at upload (G30).

`connectors` has no `org` access, so speaker rows are seeded with `user_id`
NULL — resolving a display name to a real user (fuzzy-match against
`users.name`) is a separate confirm step (`confirm_speaker`), not something
this parser can do blind. Window flush + linkage is `ingestion`'s job
(interface #7) — out of scope here.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePath

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import Message, SpeakerMap, Upload


class UnsupportedTranscriptType(ValueError):
    """[EVM-011] transcripts are `.txt`/`.md` only — enforced here (the one
    write path), not just hinted at by the FE's file-picker filter.
    """


_ALLOWED_SUFFIXES = (".txt", ".md")

_TURN_RE = re.compile(r"^\[(\d{2}):(\d{2})\]\s+([^:]+):\s*(.*)$")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Turn ids are allocated in a disjoint range from replay's line-number ids
# (data-v2 corpus ids top out at ~500) so the two sources can never collide
# in the shared `messages` table. Not a real sequence — fine for the demo's
# scale; revisit if uploads need to be numerous.
_ID_BASE = 1_000_000
_ID_STRIDE = 1_000


class TranscriptConnector:
    def __init__(self, session: Session):
        self.session = session

    def upload(self, *, filename: str, content: str, uploaded_by: int,
               mime: str = "text/plain") -> int:
        """Parse `content`, store an `Upload` row (versioned by filename),
        `Message` rows (source="transcript"), and a `SpeakerMap` row per
        distinct speaker seen. Returns the upload id.

        Raises `UnsupportedTranscriptType` for anything but `.txt`/`.md`
        [EVM-011]; `mime` is recorded as metadata, the extension is the gate.
        """
        suffix = PurePath(filename).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise UnsupportedTranscriptType(
                f"unsupported transcript type {suffix or filename!r} — .txt/.md only [EVM-011]"
            )
        upload = Upload(
            filename=filename, mime=mime, uploaded_at=datetime.now(timezone.utc),
            uploaded_by=uploaded_by, version=self._next_version(filename),
        )
        self.session.add(upload)
        self.session.flush()

        meeting_date = self._infer_date(content, filename)
        turns = self._parse_turns(content)
        seen_speakers: set[str] = set()
        for index, (minutes, seconds, speaker, text) in enumerate(turns):
            message = Message(
                id=_ID_BASE + upload.id * _ID_STRIDE + index,
                source="transcript",
                group_id=None,
                author_identity=speaker,
                # NOTE: the fixture gives no exact meeting-start clock time, only
                # a date + relative [MM:SS] offsets — this anchors turns to
                # midnight of the meeting date, which preserves correct
                # ordering/spacing but not real wall-clock time.
                ts=meeting_date + timedelta(minutes=minutes, seconds=seconds),
                text=text,
                thread_ref=None,
                raw_ref=f"{filename}:{index + 2}",  # +2: 1-indexed, header line first
                kind="text",
            )
            self.session.add(message)
            if speaker not in seen_speakers:
                seen_speakers.add(speaker)
                self.session.add(SpeakerMap(
                    upload_id=upload.id, display_name=speaker, user_id=None,
                ))
        self.session.flush()
        return upload.id

    def confirm_speaker(self, upload_id: int, display_name: str, user_id: int) -> None:
        """G30 — a lead confirms "Linh" (transcript display name) == user 42."""
        row = self.session.scalars(
            select(SpeakerMap)
            .where(SpeakerMap.upload_id == upload_id)
            .where(SpeakerMap.display_name == display_name)
        ).first()
        if row is None:
            raise LookupError(f"no speaker {display_name!r} on upload {upload_id}")
        row.user_id = user_id

    def _next_version(self, filename: str) -> int:
        existing = self.session.scalars(
            select(Upload).where(Upload.filename == filename)
        ).all()
        return (max((u.version for u in existing), default=0)) + 1

    def _infer_date(self, content: str, filename: str) -> datetime:
        match = _DATE_RE.search(filename) or _DATE_RE.search(content.splitlines()[0])
        if not match:
            raise ValueError("could not infer a meeting date from filename or header")
        return datetime.fromisoformat(match.group(1)).replace(tzinfo=timezone.utc)

    def _parse_turns(self, content: str) -> list[tuple[int, int, str, str]]:
        turns = []
        for line in content.splitlines():
            match = _TURN_RE.match(line.strip())
            if not match:
                continue
            minutes, seconds, speaker, text = match.groups()
            turns.append((int(minutes), int(seconds), speaker.strip(), text.strip()))
        return turns

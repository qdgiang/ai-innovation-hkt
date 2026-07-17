"""F3 — meeting-transcript ingestion adapter.

Parses a speaker-labelled transcript into canonical Messages: a `#` header line,
then one turn per line in the form `[MM:SS] Name: text`. One Message per turn,
source="transcript", channel="meeting/<date>".
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ai.schemas import Message, Source

TURN_RE = re.compile(r"^\[(\d{2}):(\d{2})\]\s+([^:]+):\s*(.+)$")


def parse_transcript(path: Path, start: dt.datetime, team: str | None = None) -> list[Message]:
    """Parse one transcript file; `start` (tz-aware) anchors the MM:SS offsets."""
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    date = start.date().isoformat()
    turns: list[Message] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            m = TURN_RE.match(line.strip())
            if not m:
                continue  # header / blank lines
            minutes, seconds, speaker, text = m.groups()
            turns.append(
                Message(
                    id=f"mt-{date}-{len(turns) + 1:03d}",
                    source=Source.TRANSCRIPT,
                    channel=f"meeting/{date}",
                    team=team,
                    author=speaker.strip().lower(),
                    ts=start + dt.timedelta(minutes=int(minutes), seconds=int(seconds)),
                    text=text.strip(),
                    thread_ref=None,
                    raw_ref=f"{path.name}:{lineno}",
                )
            )
    return turns

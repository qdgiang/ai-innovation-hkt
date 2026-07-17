"""F2 — seed/replay ingestion adapter.

Reads the checked-in synthetic corpus (data/corpus.jsonl, one canonical Message
per line, source="replay") through the same code path as live ingestion.
Replay pacing (feed messages gradually for the live demo) lands in Phase 1.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ai.schemas import Message


def iter_corpus(path: Path) -> Iterator[Message]:
    """Yield canonical Messages from a corpus JSONL file, in file order."""
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield Message.model_validate_json(line)

"""F5 — marker-based capture (Phase 1).

Deterministic regex path: `!decision ...` / `!blocked ...` / `!status ...`
messages become records directly. Human-asserted = 100% precision.
"""

from __future__ import annotations

from ai.schemas import ExtractedRecord, Message

MARKERS = ("!decision", "!blocked", "!status")


def extract_marked(message: Message) -> ExtractedRecord | None:
    """Return the record a marker message asserts, or None for unmarked messages."""
    raise NotImplementedError("Phase 1 (F5)")

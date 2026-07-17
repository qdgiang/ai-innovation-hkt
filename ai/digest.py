"""F7 — weekly digest generator (Phase 1 minimal).

Pure function: records in -> Markdown digest out, every line cited. Grounded
strictly on records, never on raw chat.
"""

from __future__ import annotations

from collections.abc import Sequence

from ai.schemas import Record


def render_digest(records: Sequence[Record], team: str | None = None) -> str:
    raise NotImplementedError("Phase 1 (F7 minimal)")

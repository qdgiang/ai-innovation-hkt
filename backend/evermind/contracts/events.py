"""Domain event catalog — appended by `decisions` (A) in the same transaction as
the write; consumed only by projections (`tasks`/`signals`/`surfacing`/`knowledge`,
all B except knowledge). Event shape changes are contract PRs, never silent
(work-split.md §A<->B interfaces, item 3).

Projections track their own read position in a `projection_offsets` row keyed by
consumer name — see `evermind.decisions.models.ProjectionOffset`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class DomainEvent(BaseModel):
    seq: int
    ts: datetime
    kind: str
    aggregate: str  # e.g. "decision", "task_update", "signal", "reaction_act"
    aggregate_id: int
    payload: dict[str, Any]
    caused_by_command: str | None = None  # client_command_id


EventKind = Literal[
    "decision_proposed",
    "decision_effective",
    "decision_superseded",
    "decision_rejected",
    "task_update_recorded",
    "signal_recorded",
    "signal_promoted",
    "signal_expired",
    "corroboration_appended",
    "reaction_act_registered",
]

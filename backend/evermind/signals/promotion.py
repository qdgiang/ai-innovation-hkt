"""Owner: B. SIG-1 promotion rule (design-v2.md §Signals, G27): pure decision
logic, kept separate from the DB/org/decisions wiring in `service.py` so the
rule itself — the actual business value — is testable without any of the
modules it eventually has to call that don't exist yet (org, decisions).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from evermind.contracts.enums import SignalKind
from evermind.signals.models import Signal

DEFAULT_STALENESS_DAYS = 7
MIN_CORROBORATING = 2


@dataclass
class PromotionDecision:
    """What SIG-1 promotion would submit — a `blocked` state proposal for
    `blocker` signals, a `requested` dependency edge for `dependency` signals.
    Citations = ALL accumulated mentions (G27 — this is what catches an
    implicit, never-marked blocker like data-v2's B-2).
    """

    kind: SignalKind
    project_id: int
    task_id: int | None
    party_id: int | None
    normalized_topic: str
    since: datetime
    citation_message_ids: list[int] = field(default_factory=list)


def evaluate(signals: list[Signal], *, now: datetime,
             staleness_days: int = DEFAULT_STALENESS_DAYS) -> PromotionDecision | None:
    """`signals` = every OPEN signal for one [EVM-013] identity, oldest first
    (`SignalsService.open_signals_for_identity`'s contract). Promotes when
    ≥2 corroborating mentions exist, OR a single mention has gone stale
    (design-v2.md: "1 + staleness"). One mention alone, not yet stale, never
    promotes — the ledger's whole point is not to trigger on a single
    passing remark (X-2's punishment for trigger-happiness).
    """
    if not signals:
        return None

    first_ts = signals[0].ts
    # SQLite's test driver drops tzinfo despite the TIMESTAMPTZ model contract.
    if first_ts.tzinfo is None:
        first_ts = first_ts.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    corroborated = len(signals) >= MIN_CORROBORATING
    stale = len(signals) == 1 and (now - first_ts) >= timedelta(days=staleness_days)
    if not (corroborated or stale):
        return None

    first = signals[0]
    return PromotionDecision(
        kind=first.kind,
        project_id=first.project_id,
        task_id=first.task_id,
        party_id=first.party_id,
        normalized_topic=first.normalized_topic,
        since=first_ts,
        citation_message_ids=[s.message_id for s in signals],
    )

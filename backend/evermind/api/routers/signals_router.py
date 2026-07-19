"""Owner: B. GET /blockers?by=party (SIG-2 board)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.api.deps import get_session
from evermind.contracts.enums import SignalStatus
from evermind.org.models import Party
from evermind.signals.models import Signal
from evermind.tasks.service import TasksService

router = APIRouter(tags=["signals"])


@router.get("/blockers")
def list_blockers(by: str = "party", session: Session = Depends(get_session)):
    """Grouped-by-counterparty board (G22/SIG-2), two card kinds per group:

    - blocked TASKS (asserted blocked state — marker, decision, or PIC update);
    - PROMOTED SIGNALS (SIG-1: an issue voiced ≥2 times, or 1 + staleness —
      the accumulated mentions ARE its citations, G27). Task-less promotions
      surface here too: data-v2's B-2 shape.

    Party names resolve here (api may read `org`; `signals`/`tasks` may not).
    """
    party_names = {p.id: p.name for p in session.scalars(select(Party))}

    def party_label(party_id: int | None, fallback: str | None) -> str:
        if party_id is not None:
            return party_names.get(party_id, f"party:{party_id}")
        return fallback or "unspecified"

    groups: dict[str, dict] = {}

    def bucket(key: str) -> dict:
        return groups.setdefault(key, {"tasks": [], "signals": []})

    for task in TasksService(session).list_tasks(statuses=("blocked",)):
        key = party_label(task.blocked_waiting_on_party_id,
                          task.blocked_waiting_on_text)
        bucket(key)["tasks"].append({
            "task_id": task.id, "description": task.description,
            "since": task.blocked_since,
        })

    promoted = session.scalars(
        select(Signal).where(Signal.status == SignalStatus.PROMOTED)
        .order_by(Signal.ts)
    ).all()
    by_identity: dict[tuple, list[Signal]] = {}
    for signal in promoted:
        identity = (signal.project_id, signal.task_id, signal.party_id,
                    signal.normalized_topic)
        by_identity.setdefault(identity, []).append(signal)
    for (project_id, task_id, party_id, topic), mentions in by_identity.items():
        key = party_label(party_id, topic)
        bucket(key)["signals"].append({
            "topic": topic, "kind": mentions[0].kind.value,
            "project_id": project_id, "task_id": task_id,
            "since": mentions[0].ts, "mentions": len(mentions),
            "citation_message_ids": [m.message_id for m in mentions],
            "excerpt": mentions[-1].excerpt,
        })

    return groups

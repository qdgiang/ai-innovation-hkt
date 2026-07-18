"""Owner: A. GET /decisions (DSH-4 filters + show_inactive)."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from evermind.api.deps import get_session
from evermind.contracts.enums import DecisionStatus
from evermind.decisions.models import Decision, DecisionCitation
from evermind.org.service import OrgService

router = APIRouter(tags=["decisions"])

ACTIVE_STATUSES = (DecisionStatus.PROPOSED, DecisionStatus.EFFECTIVE)


def _serialize(decision: Decision, citations: list[DecisionCitation],
               handles: dict[int, str | None]) -> dict:
    return {
        "id": decision.id,
        "ts": decision.ts,
        "recorded_at": decision.recorded_at,
        "decided_by_user_id": decision.decided_by_user_id,
        "decided_by_handle": handles.get(decision.decided_by_user_id),
        # wire-compat alias (PR #45 contract tests): actor as a handle
        "decided_by": handles.get(decision.decided_by_user_id),
        "scope": decision.scope.value,
        "scope_target": decision.scope_target,
        "description": decision.description,
        "context": decision.context,
        "note": decision.note,
        "ops": decision.ops,
        "status": decision.status.value,
        "rejected_reason": decision.rejected_reason.value if decision.rejected_reason else None,
        "supersedes_decision_id": decision.supersedes_decision_id,
        "superseded_by_decision_id": decision.superseded_by_decision_id,
        "approved_by_user_id": decision.approved_by_user_id,
        "approved_by_handle": handles.get(decision.approved_by_user_id)
        if decision.approved_by_user_id is not None else None,
        "approval_via": decision.approval_via.value if decision.approval_via else None,
        "created_from": decision.created_from.value,
        "confidence": decision.confidence,
        "effect_window": (
            {"from": decision.effect_window_from, "until": decision.effect_window_until}
            if decision.effect_window_from is not None else None
        ),
        "citations": [
            {"message_id": c.message_id, "kind": c.kind.value} for c in citations
        ],
    }


@router.get("/decisions")
def list_decisions(
    session: Session = Depends(get_session),
    scope: str | None = None,
    q: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    user: str | None = None,
    show_inactive: bool = False,
    limit: int = 200,
):
    """DSH-4 filter matrix: `scope` matches a target ("task:2") or a scope kind
    ("task"); `q` is a text search over description/context/note; `from_`/`to`
    bound event time; `user` is a handle (or numeric id) of the maker;
    `show_inactive` adds superseded/rejected history rows.
    """
    stmt = select(Decision)
    if not show_inactive:
        stmt = stmt.where(Decision.status.in_(ACTIVE_STATUSES))
    if scope:
        if ":" in scope:
            stmt = stmt.where(Decision.scope_target == scope)
        else:
            stmt = stmt.where(Decision.scope == scope)
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(or_(
            Decision.description.ilike(needle),
            Decision.context.ilike(needle),
            Decision.note.ilike(needle),
        ))
    if from_:
        stmt = stmt.where(Decision.ts >= datetime.fromisoformat(from_))
    if to:
        stmt = stmt.where(Decision.ts <= datetime.fromisoformat(to))
    if user:
        if user.isdigit():
            stmt = stmt.where(Decision.decided_by_user_id == int(user))
        else:
            maker = OrgService(session).get_user_by_handle(user)
            stmt = stmt.where(Decision.decided_by_user_id == (maker.id if maker else -1))

    decisions = list(session.scalars(
        stmt.order_by(Decision.ts.desc(), Decision.id.desc()).limit(limit)
    ))

    citation_rows = session.scalars(
        select(DecisionCitation).where(
            DecisionCitation.decision_id.in_([d.id for d in decisions] or [-1])
        )
    )
    by_decision: dict[int, list[DecisionCitation]] = {}
    for row in citation_rows:
        by_decision.setdefault(row.decision_id, []).append(row)

    handles = {u.id: u.handle for u in OrgService(session).list_personas()}
    return [_serialize(d, by_decision.get(d.id, []), handles) for d in decisions]

"""Phân-quyền spec (settled in-session 2026-07-19): view theo project +
UI actions leave chat evidence before anything is applied.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from evermind.api.evidence import leave_dashboard_evidence
from evermind.connectors.models import Message
from evermind.contracts.commands import ApproveProposal, ProposeDecision
from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionScope
from evermind.contracts.commands import OpSpec
from evermind.org.service import OrgService


def test_view_scoping_membership_and_coordinator(db_session, org_ids, org: OrgService):
    p_tt, p_cl = org_ids["projects"]["P-TT"], org_ids["projects"]["P-CL"]
    duc = org_ids["users"]["duc"]      # TEAM-EV member -> P-TT only
    tuan = org_ids["users"]["tuan"]    # TEAM-ED member -> P-CL only
    linh = org_ids["users"]["linh"]    # coordinator -> everything

    assert org.can_view_project(duc, p_tt) is True
    assert org.can_view_project(duc, p_cl) is False
    assert org.can_view_project(tuan, p_tt) is False
    assert org.can_view_project(linh, p_tt) is True
    assert org.can_view_project(linh, org_ids["projects"]["P-4AE"]) is True
    assert set(org.project_ids_of_user(tuan)) == {p_cl}


def test_dashboard_command_leaves_evidence_message_first(db_session, org_ids):
    command = ApproveProposal(
        client_command_id=uuid.uuid4(), persona="linh",
        created_from=CreatedFrom.DASHBOARD, decision_id=424242,
        approved_by_user_id=org_ids["users"]["linh"], ack_revalidation=True,
    )

    stamped = leave_dashboard_evidence(db_session, command)

    message = db_session.scalar(select(Message).where(
        Message.raw_ref == f"dashboard:{command.client_command_id}"))
    assert message is not None
    assert message.source == "dashboard"
    assert "duyệt đề xuất #424242" in message.text
    assert stamped.source_message_id == message.id

    # idempotent: a retried command reuses the same evidence row
    again = leave_dashboard_evidence(db_session, command)
    assert again.source_message_id == message.id
    rows = db_session.scalars(select(Message).where(
        Message.source == "dashboard")).all()
    assert len(rows) == 1


def test_dashboard_proposal_gains_an_evidence_citation(db_session, org_ids):
    command = ProposeDecision(
        client_command_id=uuid.uuid4(), persona="linh",
        created_from=CreatedFrom.DASHBOARD,
        decided_by_user_id=org_ids["users"]["linh"],
        scope=DecisionScope.TASK, scope_target="NEW_TASK",
        description="Chốt thuê âm thanh", citations=[],
        ops=[OpSpec(target="NEW_TASK", facet="description", op="set",
                    value="Chốt thuê âm thanh")],
        context_group_id=org_ids["groups"]["G-TT"],
    )

    stamped = leave_dashboard_evidence(db_session, command)

    assert len(stamped.citations) == 1
    assert stamped.citations[0].kind is CitationKind.EVIDENCE
    assert stamped.citations[0].message_id == stamped.source_message_id
    message = db_session.get(Message, stamped.source_message_id)
    assert message.group_id == org_ids["groups"]["G-TT"]  # routed to the project

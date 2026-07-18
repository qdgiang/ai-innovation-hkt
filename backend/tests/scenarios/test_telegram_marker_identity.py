"""ING-6 — platform-adapted author resolution on the marker path
(ingestion/identity.py): telegram authors resolve via `user_identities`
([D5], never display names), strangers land in the provisional lane (G44),
and the replay/handle lane is untouched (covered by test_marker_e2e).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from evermind.connectors.models import Message
from evermind.contracts.enums import UserStatus
from evermind.ingestion.service import IngestionService
from evermind.org.models import UserIdentity, UserTeam
from evermind.org.service import OrgService


def _telegram_message(db_session, group_id: int, author_identity: str,
                      text: str, *, mid: int,
                      author_platform_id: str | None = None) -> Message:
    message = Message(
        id=mid, source="telegram", group_id=group_id,
        author_identity=author_identity, author_platform_id=author_platform_id,
        ts=datetime.now(timezone.utc) + timedelta(days=30),
        text=text, thread_ref=None, raw_ref=f"telegram:-1001:{mid}", kind="text",
    )
    db_session.add(message)
    db_session.flush()
    return message


def test_telegram_author_resolves_via_user_identities(db_session, org_ids):
    db_session.add(UserIdentity(
        user_id=org_ids["users"]["linh"], platform="telegram",
        connector_scope="default", platform_user_id="linh_tg",
    ))
    message = _telegram_message(
        db_session, org_ids["groups"]["G-TT"], "linh_tg",
        "!decision Chốt 100 lồng đèn giấy", mid=2_000_000_301,
    )

    outcome = IngestionService(db_session).apply_markers(message.id)

    # linh (lead of the group's team) resolved via the [D5] key, not her handle
    assert outcome[0]["status"] == "effective"


def test_numeric_platform_id_beats_a_changed_username(db_session, org_ids):
    """Seen live: a member seeded as one username actually posts under another.
    The numeric platform id is the [D5] key, so resolution must not care."""
    message = _telegram_message(
        db_session, org_ids["groups"]["G-4AE"], "someone_renamed",
        "!blocked chưa đặt được sân", mid=2_000_000_305,
        author_platform_id="1210670436",  # minhpq's real telegram id (org.json)
    )

    outcome = IngestionService(db_session).apply_markers(message.id)

    # resolved to the seeded minhpq (lead of the group's team -> effective),
    # NOT to a provisional twin
    assert outcome[0]["status"] == "effective"
    user = OrgService(db_session).resolve_identity("telegram", "default", "1210670436")
    assert user is not None and user.handle == "minhpq"
    assert user.status == UserStatus.ACTIVE  # no provisional twin was created


def test_unknown_telegram_author_becomes_provisional_not_lost(db_session, org_ids):
    message = _telegram_message(
        db_session, org_ids["groups"]["G-TT"], "stranger_tg",
        "!blocked thiếu 20 đèn lồng", mid=2_000_000_302,
    )

    outcome = IngestionService(db_session).apply_markers(message.id)

    # G44: captured as a proposal awaiting the team's lead, never dropped
    assert outcome[0]["status"] == "proposed"
    user = OrgService(db_session).resolve_identity("telegram", "default", "stranger_tg")
    assert user is not None
    assert user.status == UserStatus.PROVISIONAL
    # joined to the group's team as a member
    team_row = db_session.scalar(select(UserTeam).where(UserTeam.user_id == user.id))
    assert team_row is not None and team_row.role_in_team == "member"


def test_provisional_author_is_reused_never_duplicated(db_session, org_ids):
    first = _telegram_message(
        db_session, org_ids["groups"]["G-TT"], "stranger_tg",
        "!blocked thiếu 20 đèn lồng", mid=2_000_000_303,
    )
    second = _telegram_message(
        db_session, org_ids["groups"]["G-TT"], "stranger_tg",
        "!blocked xe tải hỏng chưa có xe thay", mid=2_000_000_304,
    )

    IngestionService(db_session).apply_markers(first.id)
    IngestionService(db_session).apply_markers(second.id)

    identities = db_session.scalars(select(UserIdentity).where(
        UserIdentity.platform == "telegram",
        UserIdentity.platform_user_id == "stranger_tg",
    )).all()
    assert len(identities) == 1

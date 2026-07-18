"""L1 — CAP-4 Telegram connector (plan.md P6, T2). No real network: a fake
HTTP client stands in for `httpx`, matching `TelegramConnector`'s narrow
`HttpClient` protocol.
"""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import GroupMember, Message, MessageRevision
from evermind.connectors.telegram import TelegramConnector
from evermind.org.models import UserIdentity
from evermind.org.service import OrgService


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeHttpClient:
    def __init__(self, payload: dict):
        self._payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, *, params: dict) -> FakeResponse:
        self.calls.append((url, params))
        return FakeResponse(self._payload)


def test_poll_updates_stores_a_message_and_advances_offset(db_session: Session):
    http = FakeHttpClient({
        "ok": True,
        "result": [{
            "update_id": 100,
            "message": {
                "message_id": 5, "from": {"id": 111, "username": "linh"},
                "chat": {"id": -1001, "type": "supergroup"},
                "date": 1735689600, "text": "chào cả nhà",
            },
        }],
    })
    connector = TelegramConnector(db_session, "fake-token", http=http,
                                   chat_group_ids={"-1001": 7})
    next_offset = connector.poll_updates()

    assert next_offset == 101
    messages = db_session.scalars(select(Message).where(Message.source == "telegram")).all()
    assert len(messages) == 1
    assert messages[0].author_identity == "linh"
    assert messages[0].author_platform_id == "111"  # [D5] the stable resolution key
    assert messages[0].group_id == 7
    assert messages[0].text == "chào cả nhà"


def test_poll_updates_preserves_mention_provenance_and_capture_time(db_session: Session):
    """Entity metadata is retained for later, identity-safe extraction."""
    http = FakeHttpClient({
        "ok": True,
        "result": [{
            "update_id": 100,
            "message": {
                "message_id": 5, "from": {"id": 111, "username": "linh"},
                "chat": {"id": -1001, "type": "supergroup"},
                "date": 1735689600, "text": "@linh asks Alice and Bob",
                "entities": [
                    {"type": "mention", "offset": 0, "length": 5},
                    {"type": "text_mention", "offset": 11, "length": 5,
                     "user": {"id": 222, "username": "alice", "first_name": "Alice"}},
                    {"type": "text_link", "offset": 21, "length": 3,
                     "url": "tg://user?id=333"},
                ],
            },
        }],
    })

    TelegramConnector(db_session, "fake-token", http=http).poll_updates()

    message = db_session.scalar(select(Message).where(Message.source == "telegram"))
    assert message is not None
    assert message.captured_at is not None
    assert message.mentions == [
        {"platform_user_id": None, "username": "linh", "display_name": "@linh", "source": "mention"},
        {"platform_user_id": "222", "username": "alice", "display_name": "Alice", "source": "text_mention"},
        {"platform_user_id": "333", "username": None, "display_name": "Bob", "source": "tg://user"},
    ]


def test_telegram_username_alias_is_learned_only_from_stable_author_identity(db_session: Session, org_ids):
    linh_id = org_ids["users"]["linh"]
    db_session.add(UserIdentity(
        user_id=linh_id, platform="telegram", connector_scope="default",
        platform_user_id="111",
    ))
    db_session.flush()

    payload = {
        "ok": True,
        "result": [{
            "update_id": 1,
            "message": {
                "message_id": 1, "from": {"id": 111, "username": "learned_handle"},
                "chat": {"id": -1001}, "date": 1735689600, "text": "hello",
            },
        }],
    }
    TelegramConnector(db_session, "fake-token", http=FakeHttpClient(payload)).poll_updates()

    assert OrgService(db_session).resolve_username_alias(
        "telegram", "default", "learned_handle"
    ).id == linh_id


def test_telegram_username_alias_collision_is_unresolved(db_session: Session, org_ids):
    db_session.add_all([
        UserIdentity(user_id=org_ids["users"]["linh"], platform="telegram",
                     connector_scope="default", platform_user_id="111"),
        UserIdentity(user_id=org_ids["users"]["mai"], platform="telegram",
                     connector_scope="default", platform_user_id="222"),
    ])
    db_session.flush()
    for update_id, user_id in ((1, 111), (2, 222)):
        TelegramConnector(db_session, "fake-token", http=FakeHttpClient({
            "ok": True,
            "result": [{
                "update_id": update_id,
                "message": {
                    "message_id": update_id,
                    "from": {"id": user_id, "username": "reused_handle"},
                    "chat": {"id": -1001}, "date": 1735689600, "text": "hello",
                },
            }],
        })).poll_updates()

    assert OrgService(db_session).resolve_username_alias(
        "telegram", "default", "reused_handle"
    ) is None


def test_unknown_telegram_author_never_learns_a_handle_alias(db_session: Session, org_ids):
    """A matching display handle is not evidence of platform identity."""
    payload = {
        "ok": True,
        "result": [{
            "update_id": 1,
            "message": {
                "message_id": 1, "from": {"id": 999, "username": "linh"},
                "chat": {"id": -1001}, "date": 1735689600, "text": "hello",
            },
        }],
    }
    TelegramConnector(db_session, "fake-token", http=FakeHttpClient(payload)).poll_updates()

    assert OrgService(db_session).resolve_username_alias("telegram", "default", "linh") is None


def test_telegram_synthetic_ids_are_deterministic():
    script = (
        "from evermind.connectors.telegram import TelegramConnector; "
        "print(TelegramConnector._synthetic_id({'chat': {'id': -1001}, 'message_id': 5}))"
    )
    outputs = [
        subprocess.check_output(
            [sys.executable, "-c", script], text=True,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
        ).strip()
        for hash_seed in ("1", "2")
    ]
    assert outputs[0] == outputs[1]


def test_poll_updates_resolves_reply_to_message(db_session: Session):
    http = FakeHttpClient({
        "ok": True,
        "result": [
            {"update_id": 1, "message": {
                "message_id": 1, "from": {"id": 111, "username": "linh"},
                "chat": {"id": -1001}, "date": 1735689600, "text": "quyết định X",
            }},
            {"update_id": 2, "message": {
                "message_id": 2, "from": {"id": 222, "username": "mai"},
                "chat": {"id": -1001}, "date": 1735689650, "text": "ok chốt",
                "reply_to_message": {"chat": {"id": -1001}, "message_id": 1},
            }},
        ],
    })
    connector = TelegramConnector(db_session, "fake-token", http=http)
    connector.poll_updates()

    reply = db_session.scalars(
        select(Message).where(Message.text == "ok chốt")
    ).first()
    original = db_session.scalars(
        select(Message).where(Message.text == "quyết định X")
    ).first()
    assert reply.thread_ref == original.id


def test_poll_updates_tracks_membership_join_and_leave(db_session: Session):
    # user id deliberately > int32: modern telegram ids overflow INTEGER —
    # regression for the live NumericValueOutOfRange crash (BigInteger column)
    http = FakeHttpClient({
        "ok": True,
        "result": [{
            "update_id": 1, "my_chat_member": {
                "chat": {"id": -1001}, "date": 1735689600,
                "new_chat_member": {"user": {"id": 6837466799, "username": "khoa"}, "status": "member"},
            },
        }],
    })
    connector = TelegramConnector(db_session, "fake-token", http=http,
                                   chat_group_ids={"-1001": 7})
    connector.poll_updates()

    member = db_session.get(GroupMember, {"group_id": 7, "user_id": 6837466799})
    assert member is not None
    assert member.left_at is None

    http_leave = FakeHttpClient({
        "ok": True,
        "result": [{
            "update_id": 2, "my_chat_member": {
                "chat": {"id": -1001}, "date": 1735689700,
                "new_chat_member": {"user": {"id": 6837466799, "username": "khoa"}, "status": "left"},
            },
        }],
    })
    TelegramConnector(db_session, "fake-token", http=http_leave,
                       chat_group_ids={"-1001": 7}).poll_updates()
    db_session.flush()  # poll_updates() leaves flush/commit to the caller
    db_session.refresh(member)
    assert member.left_at is not None


def test_poll_updates_dedups_redelivery_and_hooks_only_new_messages(db_session: Session):
    """Restart shape: the in-memory offset is gone, Telegram re-delivers the
    same update — raw_ref dedup stores it once and the hook fires once."""
    payload = {
        "ok": True,
        "result": [{
            "update_id": 100,
            "message": {
                "message_id": 5, "from": {"id": 111, "username": "linh"},
                "chat": {"id": -1001, "type": "supergroup"},
                "date": 1735689600, "text": "!blocked thiếu 20 đèn lồng",
            },
        }],
    }
    hooked: list[int] = []
    TelegramConnector(db_session, "fake-token", http=FakeHttpClient(payload),
                       chat_group_ids={"-1001": 7}).poll_updates(on_message=hooked.append)
    TelegramConnector(db_session, "fake-token", http=FakeHttpClient(payload),
                       chat_group_ids={"-1001": 7}).poll_updates(on_message=hooked.append)

    messages = db_session.scalars(select(Message).where(Message.source == "telegram")).all()
    assert len(messages) == 1
    assert hooked == [messages[0].id]  # flushed id, fired exactly once


def test_edited_message_appends_a_revision_never_overwrites(db_session: Session):
    """G45 via the live path: an edit bumps current_rev and appends a
    message_revisions row through the service port."""
    original = {
        "ok": True,
        "result": [{
            "update_id": 1,
            "message": {
                "message_id": 9, "from": {"id": 111, "username": "linh"},
                "chat": {"id": -1001}, "date": 1735689600, "text": "giá 12k",
            },
        }],
    }
    edit = {
        "ok": True,
        "result": [{
            "update_id": 2,
            "edited_message": {
                "message_id": 9, "from": {"id": 111, "username": "linh"},
                "chat": {"id": -1001}, "date": 1735689600,
                "edit_date": 1735689700, "text": "giá 16k",
            },
        }],
    }
    TelegramConnector(db_session, "fake-token", http=FakeHttpClient(original),
                       chat_group_ids={"-1001": 7}).poll_updates()
    TelegramConnector(db_session, "fake-token", http=FakeHttpClient(edit),
                       chat_group_ids={"-1001": 7}).poll_updates()

    message = db_session.scalars(
        select(Message).where(Message.raw_ref == "telegram:-1001:9")
    ).one()
    assert message.current_rev == 2
    assert message.text == "giá 16k"
    revision = db_session.scalars(
        select(MessageRevision).where(MessageRevision.message_id == message.id)
    ).one()
    assert (revision.rev, revision.text) == (2, "giá 16k")


def test_edit_of_a_message_captured_before_the_bot_joined_is_dropped(db_session: Session):
    edit_only = {
        "ok": True,
        "result": [{
            "update_id": 3,
            "edited_message": {
                "message_id": 77, "from": {"id": 111, "username": "linh"},
                "chat": {"id": -1001}, "date": 1735689600,
                "edit_date": 1735689700, "text": "sửa tin nhắn cũ",
            },
        }],
    }
    TelegramConnector(db_session, "fake-token", http=FakeHttpClient(edit_only),
                       chat_group_ids={"-1001": 7}).poll_updates()
    assert db_session.scalars(select(Message)).all() == []


def test_poll_updates_passes_offset_to_the_next_call(db_session: Session):
    http = FakeHttpClient({"ok": True, "result": []})
    TelegramConnector(db_session, "fake-token", http=http).poll_updates(offset=42)
    assert http.calls[0][1]["offset"] == 42


# ---------------------------------------------------------------------------
# L3 — the no-send guard (testing-strategy.md §L3, structural enforcement of
# settled #20: read-only capture is the whole permission story)
# ---------------------------------------------------------------------------


def test_telegram_connector_exposes_no_send_method():
    forbidden = {"send", "send_message", "sendmessage", "post", "reply"}
    public_methods = {
        name for name in dir(TelegramConnector) if not name.startswith("_")
    }
    assert not (public_methods & forbidden), (
        f"TelegramConnector must never gain a send-capable method; found {public_methods & forbidden}"
    )

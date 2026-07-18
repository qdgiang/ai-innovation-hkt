"""Owner: B. CAP-4 — Telegram live connector: long-polling `getUpdates`.

NEVER SENDS (settled #20 — read-only capture is also the whole permission
story). This class intentionally exposes no send/post method; L3's no-send
guard test asserts that structurally, and CI greps Bot-API send-method names
out of `connectors/` (testing-strategy.md §L3 — so never write those tokens
literally anywhere in this package, docstrings included).

Runbook facts (can't be verified live in this sandbox — no real bot token):
privacy mode must be disabled via BotFather *before* joining the group; bots
cannot backfill history (CAP-2/replay covers it); a group's `migrate_to_
chat_id` field (Telegram's group->supergroup upgrade) needs the same
permanent-`chat_groups.id` remapping care as G53 describes — recognized
here (chat ids resolve per-update via `_resolve_group_id`) but not remapped,
since that write is `org`'s job.

Restart safety: the `getUpdates` offset lives with the CALLER (in-memory in
the api lifespan loop); Telegram re-delivers unacknowledged updates after a
restart, so `_store_message` dedups on `raw_ref` — the same idempotency
contract as replay's `_already_ingested`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import GroupMember, Message
from evermind.connectors.service import ConnectorsService


class HttpClient(Protocol):
    """The only shape this module needs from an HTTP client — narrow on
    purpose so tests can inject a fake without pulling in real httpx/network.
    """

    def get(self, url: str, *, params: dict) -> "HttpResponse": ...


class HttpResponse(Protocol):
    def json(self) -> dict: ...


class TelegramConnector:
    """Read-only. Do not add a send/post/reply method to this class."""

    def __init__(self, session: Session, bot_token: str, *, http: HttpClient,
                 chat_group_ids: dict[str, int] | None = None):
        self.session = session
        self._bot_token = bot_token
        self._http = http
        self._chat_group_ids = chat_group_ids or {}

    def poll_updates(self, *, offset: int | None = None,
                     on_message: Callable[[int], None] | None = None) -> int:
        """One `getUpdates` call -> normalized `messages`/`group_members` rows.
        Returns the highest `update_id` seen (the next call's `offset`), or
        the passed-in `offset` unchanged if nothing new arrived.

        `on_message` fires once per NEWLY stored message, after a flush (so
        the id is readable back) — the composition root hooks the marker lane
        here, mirroring replay's callback. Dedup'd redeliveries never fire it.
        """
        url = f"https://api.telegram.org/bot{self._bot_token}/getUpdates"
        params: dict = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        response = self._http.get(url, params=params)
        body = response.json()

        next_offset = offset
        for update in body.get("result", []):
            next_offset = max(next_offset or 0, update["update_id"] + 1)
            self._apply_update(update, on_message)
        return next_offset or (offset or 0)

    def _apply_update(self, update: dict,
                      on_message: Callable[[int], None] | None) -> None:
        if "message" in update:
            self._store_message(update["message"], kind="text", on_message=on_message)
        elif "edited_message" in update:
            self._store_edit(update["edited_message"])
        elif "my_chat_member" in update:
            self._store_membership(update["my_chat_member"])
        elif "chat_member" in update:
            self._store_membership(update["chat_member"])
        # reaction updates (message_reaction) intentionally not handled yet —
        # G67 requires the tracked-message lookup (decisions.service,
        # interface #8), not wired in this pass.

    def _resolve_group_id(self, chat: dict) -> int | None:
        return self._chat_group_ids.get(str(chat["id"]))

    @staticmethod
    def _raw_ref(msg: dict) -> str:
        return f"telegram:{msg['chat']['id']}:{msg['message_id']}"

    def _already_ingested(self, raw_ref: str) -> bool:
        return self.session.scalar(
            select(Message.id).where(Message.raw_ref == raw_ref)
        ) is not None

    def _store_message(self, msg: dict, *, kind: str,
                       on_message: Callable[[int], None] | None = None) -> None:
        raw_ref = self._raw_ref(msg)
        if self._already_ingested(raw_ref):
            return  # restart redelivery (in-memory offset) — idempotent skip
        from_user = msg.get("from", {})
        message = Message(
            id=self._synthetic_id(msg),
            source="telegram",
            group_id=self._resolve_group_id(msg["chat"]),
            author_identity=from_user.get("username") or str(from_user.get("id", "unknown")),
            author_platform_id=str(from_user["id"]) if "id" in from_user else None,
            ts=datetime.fromtimestamp(msg["date"], tz=timezone.utc),
            text=msg.get("text", ""),
            thread_ref=self._synthetic_id(msg["reply_to_message"])
            if msg.get("reply_to_message") else None,
            raw_ref=raw_ref,
            kind=kind,
        )
        self.session.add(message)
        self.session.flush()
        if on_message is not None:
            on_message(message.id)

    def _store_edit(self, msg: dict) -> None:
        """G45: edits append a `message_revisions` row via the service port,
        never overwrite in place. An edit to a message captured before the bot
        joined (no `raw_ref` match) has nothing to revise and is dropped.
        """
        existing = self.session.scalar(
            select(Message).where(Message.raw_ref == self._raw_ref(msg))
        )
        if existing is None:
            return
        edited_at = datetime.fromtimestamp(
            msg.get("edit_date", msg["date"]), tz=timezone.utc
        )
        ConnectorsService(self.session).apply_edit(
            existing.id, msg.get("text", ""), edited_at
        )

    def _store_membership(self, event: dict) -> None:
        chat = event["chat"]
        user = event["new_chat_member"]["user"]
        status = event["new_chat_member"]["status"]
        joined_at = datetime.fromtimestamp(event["date"], tz=timezone.utc)
        existing = self.session.get(GroupMember, {
            "group_id": self._resolve_group_id(chat) or -1, "user_id": user["id"],
        })
        if status in ("left", "kicked"):
            if existing is not None:
                existing.left_at = joined_at
        elif existing is None:
            self.session.add(GroupMember(
                group_id=self._resolve_group_id(chat) or -1, user_id=user["id"],
                joined_at=joined_at,
            ))

    @staticmethod
    def _synthetic_id(msg: dict) -> int:
        # Telegram's own (chat_id, message_id) pair is the real identity;
        # folded into a bounded positive range so it (a) fits the int32 PK
        # column and (b) stays disjoint from replay's/transcript's id ranges
        # — same "each source gets its own numbering scheme" as
        # connectors/transcript.py. A hash collision is theoretically
        # possible; not a concern at this system's demo scale.
        digest = hash((msg["chat"]["id"], msg["message_id"])) % 100_000_000
        return 2_000_000_000 + digest

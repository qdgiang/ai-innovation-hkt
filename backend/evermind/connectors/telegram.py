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
from hashlib import blake2s
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.connectors.models import GroupMember, Message
from evermind.connectors.service import ConnectorsService
from evermind.org.service import OrgService


TELEGRAM_CONNECTOR_SCOPE = "default"


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
        author_platform_id = str(from_user["id"]) if "id" in from_user else None
        if author_platform_id is not None and from_user.get("username"):
            OrgService(self.session).learn_username_alias_from_stable_identity(
                "telegram", TELEGRAM_CONNECTOR_SCOPE, author_platform_id,
                from_user["username"],
            )
        message = Message(
            id=self._synthetic_id(msg),
            source="telegram",
            group_id=self._resolve_group_id(msg["chat"]),
            author_identity=from_user.get("username") or str(from_user.get("id", "unknown")),
            author_platform_id=author_platform_id,
            ts=datetime.fromtimestamp(msg["date"], tz=timezone.utc),
            captured_at=datetime.now(timezone.utc),
            text=msg.get("text", ""),
            mentions=self._mentions(msg),
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
        identity = f"{msg['chat']['id']}:{msg['message_id']}".encode("utf-8")
        digest = int.from_bytes(blake2s(identity, digest_size=8).digest(), "big") % 100_000_000
        return 2_000_000_000 + digest

    @staticmethod
    def _mentions(msg: dict) -> list[dict]:
        """Extract Telegram entity provenance without inferring identity."""
        text = msg.get("text", "")
        mentions: list[dict] = []
        for entity in msg.get("entities", []):
            entity_type = entity.get("type")
            display_name = TelegramConnector._entity_text(text, entity)
            if entity_type == "mention":
                username = display_name.strip().lstrip("@") or None
                mentions.append({
                    "platform_user_id": None,
                    "username": username,
                    "display_name": display_name or None,
                    "source": "mention",
                })
            elif entity_type == "text_mention" and isinstance(entity.get("user"), dict):
                user = entity["user"]
                name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
                mentions.append({
                    "platform_user_id": str(user["id"]) if "id" in user else None,
                    "username": user.get("username"),
                    "display_name": name or display_name or None,
                    "source": "text_mention",
                })
            elif entity.get("url"):
                platform_user_id = TelegramConnector._tg_user_id(entity["url"])
                if platform_user_id is not None:
                    mentions.append({
                        "platform_user_id": platform_user_id,
                        "username": None,
                        "display_name": display_name or None,
                        "source": "tg://user",
                    })
        return mentions

    @staticmethod
    def _entity_text(text: str, entity: dict) -> str:
        """Telegram entity offsets are UTF-16 code-unit offsets, not Python indexes."""
        try:
            offset = int(entity["offset"])
            length = int(entity["length"])
        except (KeyError, TypeError, ValueError):
            return ""
        if offset < 0 or length < 0:
            return ""
        encoded = text.encode("utf-16-le")
        return encoded[offset * 2:(offset + length) * 2].decode("utf-16-le", errors="ignore")

    @staticmethod
    def _tg_user_id(url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme != "tg" or parsed.netloc != "user":
            return None
        user_id = parse_qs(parsed.query).get("id", [""])[0]
        return user_id if user_id.isdigit() else None

"""Owner: B. CAP-4 glue — the live Telegram poll loop (composition root).

`connectors` may not import `org`/`ingestion` (architecture.md allowlist), so
this api-side module is where the three meet — exactly like replay's CLI
`main()`. Each beat: fresh session, rebuild the platform_chat_id →
`chat_groups.id` map from org (fresh per beat, so re-seeding while the api
runs is picked up without a restart), one `getUpdates` round, and the marker
lane fires on every newly captured message.

The offset is in-memory only: after a restart Telegram re-delivers
unacknowledged updates and the connector's `raw_ref` dedup drops them (see
connectors/telegram.py). Messages are committed BEFORE the marker command
runs, so a failed/rolled-back command never loses the capture itself.
"""
from __future__ import annotations

import logging
from typing import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from evermind.config import settings
from evermind.connectors.models import Message
from evermind.connectors.telegram import TelegramConnector
from evermind.ingestion.service import IngestionService
from evermind.org.models import ChatGroup

logger = logging.getLogger(__name__)


class TelegramPoller:
    """One instance per app lifespan; `beat()` is called from the poll thread."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory
        self._offset: int | None = None
        self._http = httpx.Client(timeout=10.0)
        self._unmapped_logged: set[str] = set()

    def beat(self) -> None:
        with self._session_factory() as session:
            ingestion = IngestionService(session)

            def on_message(message_id: int) -> None:
                session.commit()  # durable capture first — markers may roll back
                self._warn_if_unmapped(session, message_id)
                ingestion.apply_markers(message_id)

            connector = TelegramConnector(
                session,
                settings.telegram_bot_token,
                http=self._http,
                chat_group_ids=self._chat_group_ids(session),
            )
            self._offset = connector.poll_updates(offset=self._offset,
                                                  on_message=on_message)
            session.commit()

    def close(self) -> None:
        self._http.close()

    @staticmethod
    def _chat_group_ids(session: Session) -> dict[str, int]:
        rows = session.execute(
            select(ChatGroup.platform_chat_id, ChatGroup.id)
            .where(ChatGroup.platform == "telegram")
        ).all()
        return {platform_chat_id: group_id for platform_chat_id, group_id in rows}

    def _warn_if_unmapped(self, session: Session, message_id: int) -> None:
        """Ops affordance (runbook §Telegram): the group's chat id is only
        discoverable by letting the bot see one message — surface it once."""
        message = session.get(Message, message_id)
        if message is None or message.group_id is not None:
            return
        chat_id = message.raw_ref.split(":")[1]
        if chat_id not in self._unmapped_logged:
            self._unmapped_logged.add(chat_id)
            logger.warning(
                "telegram chat %s is not mapped in chat_groups — put it in "
                "org.json (platform_chat_id) and re-run the org seed", chat_id,
            )

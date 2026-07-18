"""Owner: B. CAP-4 (T2) — Telegram live connector: long-polling `getUpdates`.

NEVER SENDS (settled #20 — read-only capture is also the whole permission
story). This class intentionally exposes no send/post method; L3's no-send
guard test asserts that structurally and CI greps `sendMessage|send_message`
out of this package. STUB — P6 deliverable.
"""
from __future__ import annotations

from sqlalchemy.orm import Session


class TelegramConnector:
    """Read-only. Do not add a send/post/reply method to this class."""

    def __init__(self, session: Session, bot_token: str):
        self.session = session
        self._bot_token = bot_token

    def poll_updates(self) -> int:
        """TODO(B): long-poll getUpdates; normalize edits/media/membership/reactions
        (reactions only on tracked messages — check `decisions.service.tracked_message_ids`).
        Runbook: disable privacy mode via BotFather before joining the group; no
        backfill (CAP-2 covers history); chat-id migration absorbed here (G53).
        """
        raise NotImplementedError

"""Owner: A. ING-6 — author→user resolution, platform-adapted.

A captured `Message` names its author only as a platform-local string
(`author_identity`). This module turns that into an org `User` without
ingestion growing per-platform branches:

- live platforms (telegram today; any future connector) register a
  `PlatformAdapter` in `ADAPTERS`, keyed by `messages.source`. Resolution
  goes through `user_identities` ([D5] — the platform-scoped key, NEVER a
  display name), and a stranger lands in the provisional-user lane (G44)
  instead of dead-ending.
- every other source (replay corpus, transcript) keeps the seed convention:
  `author_identity` IS the org handle.

Adding a platform = one `ADAPTERS` entry + seeded `user_identities` rows.
No other module changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from evermind.connectors.models import Message
from evermind.org.models import User
from evermind.org.seed import CONNECTOR_SCOPE
from evermind.org.service import OrgService


@dataclass(frozen=True)
class PlatformAdapter:
    """How one platform's normalized messages expose the [D5] identity key
    and a human-readable name. The defaults fit connectors that put the
    platform user key in `author_identity` (telegram does); a future
    connector that packs it differently overrides these two methods.
    """

    platform: str
    connector_scope: str = CONNECTOR_SCOPE

    def identity_key(self, message: Message) -> str:
        # [D5] prefer the stable numeric platform id — usernames are mutable
        # display keys and may differ from what got seeded (seen live: a user
        # given as "minhpq" whose real telegram username is "pqminh").
        return message.author_platform_id or message.author_identity

    def display_name(self, message: Message) -> str:
        return message.author_identity


ADAPTERS: dict[str, PlatformAdapter] = {
    "telegram": PlatformAdapter(platform="telegram"),
}


class AuthorResolver:
    """The single author→User path for ingestion (used by the marker lane;
    the future window/extraction lane should reuse it)."""

    def __init__(self, session: Session):
        self.session = session
        self.org = OrgService(session)

    def resolve(self, message: Message, *, team_id: int | None = None) -> User | None:
        adapter = ADAPTERS.get(message.source)
        if adapter is None:
            # seed/replay/transcript lane: author_identity IS the org handle
            return self.org.get_user_by_handle(message.author_identity)
        user = self.org.resolve_identity(
            adapter.platform, adapter.connector_scope, adapter.identity_key(message)
        )
        if user is not None:
            return user
        # G44: a stranger on a live platform becomes a provisional user (rank 1,
        # joined to the group's team when known) — never silently dropped.
        return self.org.create_provisional_user(
            name=adapter.display_name(message),
            platform=adapter.platform,
            connector_scope=adapter.connector_scope,
            platform_user_id=adapter.identity_key(message),
            team_id=team_id,
        )

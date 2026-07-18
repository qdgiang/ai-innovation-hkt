"""Owner: A. Persona scoping — *who is asking*; *may they* stays domain
(architecture.md: "api does persona scoping only"). Settled #3, demo-honest:
the API trusts the persona header for scoping; real auth = T3 seam [EVM-001].
"""
from __future__ import annotations

from fastapi import Header

from evermind.db.session import get_session  # noqa: F401  (re-exported for routers)


def persona(x_persona: str = Header(...)) -> str:
    """TODO(A): validate the header names a seeded user; no session/token yet
    (demo-honest, stated on the FE switcher)."""
    return x_persona

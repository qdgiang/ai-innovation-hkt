"""Shared declarative base. Owner: A (P0), then each module owns its own tables
(architecture.md: "after 0001, each owner migrates their own tables").
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

"""Enum registry — one place, reused everywhere (data-model.md §Enum registry).

Frozen for the phase once used in a merged PR (plan.md working agreement 1).
Any change here is a `contract-change` PR reviewed by both A and B.
"""
from enum import Enum


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RejectedReason(str, Enum):
    VETO = "veto"
    OVERRULED = "overruled"
    WITHDRAWN = "withdrawn"
    DISMISSED = "dismissed"
    # NOTE: no EXPIRED — settled #18, decisions carry no TTL


class DecisionScope(str, Enum):
    TASK = "task"
    TEAM = "team"
    PROJECT = "project"


class CreatedFrom(str, Enum):
    MARKER = "marker"
    LLM = "llm"
    DASHBOARD = "dashboard"
    TRANSCRIPT = "transcript"


class ApprovalVia(str, Enum):
    AUTHORITY = "authority"
    DELEGATION = "delegation"
    SELF_CONFIRM = "self_confirm"


class CitationKind(str, Enum):
    EVIDENCE = "evidence"
    APPROVAL = "approval"
    CORROBORATION = "corroboration"


class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELED = "canceled"
    MERGED = "merged"


class TaskKind(str, Enum):
    PROJECT = "project"
    ONGOING = "ongoing"


class TaskType(str, Enum):
    URGENT = "urgent"
    NORMAL = "normal"
    UNDEFINED = "undefined"


class ProjectKind(str, Enum):
    CAMPAIGN = "campaign"
    PROGRAM = "program"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"


class UserStatus(str, Enum):
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    DEPARTING = "departing"
    DEPARTED = "departed"


class SignalKind(str, Enum):
    BLOCKER = "blocker"
    DEPENDENCY = "dependency"
    ASK = "ask"
    PARKED = "parked"


class SignalStatus(str, Enum):
    OPEN = "open"
    PROMOTED = "promoted"
    EXPIRED = "expired"


class DependencyStatus(str, Enum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    NEEDS_REWIRE = "needs_rewire"


class MessageKind(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    FILE = "file"
    VOICE = "voice"
    STICKER = "sticker"
    SYSTEM = "system"


class PartyKind(str, Enum):
    PERSON = "person"
    VENDOR = "vendor"
    INSTITUTION = "institution"


class EvidenceState(str, Enum):
    """Derived, never stored directly — computed from message + revision state. [EVM-015]"""
    LIVE = "live"
    EDITED_AFTER_CAPTURE = "edited_after_capture"
    SOURCE_DELETED = "source_deleted"
    REDACTED = "redacted"


class TaskUpdateKind(str, Enum):
    STATUS = "status"
    NOTE = "note"


class RoleRank(int, Enum):
    """Seed map (data-model.md §Org & identity)."""
    MEMBER = 1
    LEAD = 2
    COORDINATOR = 3

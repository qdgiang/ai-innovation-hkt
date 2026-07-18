"""Owner: B. The event-consumer loop — D3 read side. `decisions` (A) appends
`domain_events`; this module folds them into the `tasks` projection and never
writes anything else. Tracks its own position via
`decisions.models.ProjectionOffset` (consumer="tasks").

P1: tested against a synthetic `domain_events` stream until A's gateway lands
(plan.md P1 Lane B note).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from evermind.db.eventlog import DomainEvent

CONSUMER_NAME = "tasks"


class TasksConsumer:
    def __init__(self, session: Session):
        self.session = session

    def poll_and_apply(self) -> int:
        """TODO(B): read domain_events after this consumer's last_seq, apply each to
        the fold (TSK-1), advance ProjectionOffset in the same transaction as the
        fold write. Returns count applied.
        """
        raise NotImplementedError

    def _apply_event(self, event: DomainEvent) -> None:
        """TODO(B): dispatch on event.kind -> fold mutation (assignment ops, status
        flips from ops JSON, task_updates append, dependency edge writes). See
        design-v2.md §Facet registry for the ops vocabulary.
        """
        raise NotImplementedError

"""Writing to and reading from the audit log."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from hotel.domain.actor import Actor
from hotel.domain.audit import AuditEntry, ChainCheck, verify_chain
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.paging import Page, PageRequest
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.authorization import require_role


def record(
    uow: UnitOfWork,
    clock: Clock,
    actor: Actor,
    action: str,
    *,
    entity: str | None = None,
    entity_id: object = None,
    **details: Any,
) -> None:
    """Add an entry inside the caller's transaction.

    Because it shares the transaction, the entry is saved if and only if the
    operation it describes is saved. Details must never contain personal data
    or secrets: record ids and the names of changed fields, not their values.
    """
    uow.audit.append(
        AuditEntry(
            at=clock.now(),
            action=action,
            user_id=actor.user_id,
            username=actor.username,
            entity=entity,
            entity_id=None if entity_id is None else str(entity_id),
            details=details,
            ip=actor.ip,
        )
    )


@dataclass(frozen=True, slots=True)
class AuditFilter:
    user_id: int | None = None
    action_prefix: str | None = None
    since: date | None = None
    until: date | None = None  # inclusive


class AuditService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def search(self, actor: Actor, filters: AuditFilter, request: PageRequest) -> Page[AuditEntry]:
        require_role(actor, Role.MANAGER)
        tz = self._clock.hotel_tz

        def start_of(day: date) -> datetime:
            return datetime.combine(day, time.min, tzinfo=tz)

        with self._uow() as uow:
            return uow.audit.search(
                request,
                user_id=filters.user_id,
                action_prefix=filters.action_prefix,
                since=start_of(filters.since) if filters.since else None,
                until=start_of(filters.until + timedelta(days=1)) if filters.until else None,
            )

    def known_users(self, actor: Actor) -> list[tuple[int, str]]:
        """(id, username) pairs for the viewer's user filter."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return [(u.id, u.username) for u in uow.users.list_all()]

    def verify(self, actor: Actor) -> ChainCheck:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return verify_chain(uow.audit.iterate())

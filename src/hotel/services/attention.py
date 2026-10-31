"""What needs attention now (story 7.8): the exceptions, first, on the dashboard.

Front-desk staff and managers scan for what is wrong rather than read every
figure, so the dashboard opens with a short list that appears only when
something needs doing. Each item is already known elsewhere in the application
(the day's lists, the night audit, the backups, the audit chain); this service
only gathers them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.services.audit import AuditService
from hotel.services.backups import BackupService
from hotel.services.front_desk import FrontDeskDay
from hotel.services.night_audit import NightAuditService

BACKUP_MAX_AGE = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class AttentionItem:
    kind: str  # the template turns each kind into a sentence and a link
    count: int = 1
    level: str = "warning"  # "warning" or "danger" (something may be broken)


class AttentionService:
    def __init__(
        self,
        clock: Clock,
        night_audit: NightAuditService,
        backups: BackupService,
        audit: AuditService,
    ) -> None:
        self._clock = clock
        self._night_audit = night_audit
        self._backups = backups
        self._audit = audit

    def items(self, actor: Actor, day: FrontDeskDay) -> list[AttentionItem]:
        """Front-desk exceptions for everyone; the hotel's safety checks for managers."""
        found = []
        overdue = sum(1 for r in day.departures if r.period.departure < day.today)
        late = sum(1 for r in day.arrivals if r.period.arrival < day.today)
        not_ready = sum(1 for card in day.arrival_cards.values() if not card.ready)
        for kind, count in (
            ("overdue_departures", overdue),
            ("late_arrivals", late),
            ("rooms_not_ready", not_ready),
            ("unpaid_invoices", len(day.unpaid)),
        ):
            if count:
                found.append(AttentionItem(kind, count))
        if actor.user is not None and actor.user.is_manager:
            found.extend(self._manager_items(actor, day))
        return found

    def _manager_items(self, actor: Actor, day: FrontDeskDay) -> list[AttentionItem]:
        found = []
        last_closed = self._night_audit.last_closed_day(actor)
        if last_closed is None or last_closed < day.today - timedelta(days=1):
            found.append(AttentionItem("day_not_closed"))
        newest = max((b.created_at for b in self._backups.list(actor)), default=None)
        now = self._clock.local_now().replace(tzinfo=None)  # backup names hold local time
        if newest is None or now - newest > BACKUP_MAX_AGE:
            found.append(AttentionItem("old_backup"))
        if not self._audit.verify(actor).ok:
            found.append(AttentionItem("audit_chain_broken", level="danger"))
        return found

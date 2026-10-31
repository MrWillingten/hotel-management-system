"""The night audit: closing each finished day (story 5.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import HotelError, ValidationError
from hotel.domain.money import Money
from hotel.domain.night_audit import AuditOutcome, DailySnapshot, days_to_close
from hotel.domain.reservations import Reservation
from hotel.persistence.unit_of_work import UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role
from hotel.services.billing import bill_for
from hotel.services.reports import ReportService
from hotel.services.reservations import ReservationService


@dataclass(frozen=True, slots=True)
class AuditPreview:
    """Story 7.10: what closing `day` would do, shown before the button (nothing is written)."""

    day: date
    already_closed: bool
    no_shows: list[Reservation] = field(default_factory=list)  # will become no-shows
    overdue: list[Reservation] = field(default_factory=list)  # still in after their departure
    open_balances: int = 0  # stays in the house that still owe money
    open_total: Money = field(default_factory=Money.zero)


class NightAuditService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        reservations: ReservationService,
        reports: ReportService,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._reservations = reservations
        self._reports = reports

    def recent(self, actor: Actor) -> list[DailySnapshot]:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return uow.snapshots.recent()

    def last_closed_day(self, actor: Actor) -> date | None:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return uow.snapshots.last_closed_day()

    def preview(self, actor: Actor, day: date | None = None) -> AuditPreview:
        """The consequences of run(day), read only: the manager sees them before confirming."""
        require_role(actor, Role.MANAGER)
        today = self._clock.today()
        day = day or today - timedelta(days=1)
        with self._uow() as uow:
            if uow.snapshots.get(day) is not None:
                return AuditPreview(day, already_closed=True)
            due = [bill_for(uow, r).balance for r in uow.reservations.in_house()]
            owing = [b for b in due if not b.is_negative() and not b.is_zero()]
            return AuditPreview(
                day,
                already_closed=False,
                no_shows=uow.reservations.not_arrived(day),
                overdue=uow.reservations.departures(day),
                open_balances=len(owing),
                open_total=sum(owing, Money.zero()),
            )

    def run(self, actor: Actor, day: date | None = None) -> AuditOutcome:
        """Close `day` (yesterday by default). Running it again changes nothing."""
        require_role(actor, Role.MANAGER)
        today = self._clock.today()
        day = day or today - timedelta(days=1)
        if day >= today:
            raise ValidationError(
                "night_audit.day_not_over", fields={"day": "night_audit.day_not_over"}
            )
        with self._uow() as uow:
            existing = uow.snapshots.get(day)
            overdue = [r.code for r in uow.reservations.departures(day)]
            waiting = uow.reservations.not_arrived(day)
        if existing is not None:
            return AuditOutcome(day, existing, overdue=overdue, already_closed=True)

        # 1. Guests who never came: the day is over, so their arrival time has passed.
        no_shows = []
        for reservation in waiting:
            try:
                self._reservations.record_no_show(
                    actor, reservation.id, version=reservation.version
                )
            except HotelError:
                continue  # changed by someone in the meantime: left for the next run
            no_shows.append(reservation.code)

        # 2. The day's figures, frozen (the primary key refuses a second snapshot).
        figures = self._reports.report(actor, day, day)
        snapshot = DailySnapshot(
            day=day,
            nights_sold=figures.nights_sold,
            nights_sellable=figures.nights_sellable,
            room_value=figures.room_value,
            invoiced=figures.revenue,
            cash=figures.cash_received,
            reservations_made=figures.reservations_made,
            cancellations=figures.cancellations.count,
            # Recorded during the day by the desk, plus those recorded by this audit.
            no_shows=figures.no_shows.count + len(no_shows),
            overdue_departures=len(overdue),
            created_at=self._clock.now(),
        )
        with self._uow() as uow:
            if not uow.snapshots.add(snapshot, actor.user_id):  # someone closed it just now
                return AuditOutcome(
                    day, uow.snapshots.get(day), overdue=overdue, already_closed=True
                )
            record(
                uow,
                self._clock,
                actor,
                "night_audit.closed",
                entity="day",
                entity_id=day.isoformat(),
                no_shows=len(no_shows),
                overdue=len(overdue),
            )
            return AuditOutcome(day, uow.snapshots.get(day), no_shows, overdue)

    def catch_up(self, actor: Actor) -> list[AuditOutcome]:
        """At start-up: close every finished day that was not closed (at most a month)."""
        with self._uow() as uow:
            last = uow.snapshots.last_closed_day()
        return [self.run(actor, day) for day in days_to_close(last, self._clock.today())]

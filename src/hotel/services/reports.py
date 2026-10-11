"""Management reports (story 5.1, brief §4.8). Managers only."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.money import Money
from hotel.domain.reports import (
    CategoryAvailability,
    DayFigures,
    Report,
    nights_between,
    validate_range,
)
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.authorization import require_role
from hotel.services.billing import bill_for


class ReportService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def default_range(self) -> tuple[date, date]:
        """This month so far... and to its end: the first and last night of the month."""
        today = self._clock.today()
        first = today.replace(day=1)
        next_month = (first + timedelta(days=32)).replace(day=1)
        return first, next_month - timedelta(days=1)

    def report(
        self, actor: Actor, first: date, last: date, *, availability_day: date | None = None
    ) -> Report:
        require_role(actor, Role.MANAGER)
        first, last = validate_range(first, last)
        # Calendar days are in hotel time; stored instants are UTC.
        start, end = self._instant(first), self._instant(last + timedelta(days=1))
        availability_day = availability_day or self._clock.today()
        # One read transaction: every figure describes the same moment.
        with self._uow() as uow:
            reports = uow.reports
            in_service = reports.rooms_in_service()
            sold = reports.sold_per_night(first, last)
            closed = reports.closed_per_night(first, last)
            days = [
                DayFigures(
                    night,
                    sold.get(night, (0, Money.zero()))[0],
                    in_service - closed.get(night, 0),
                    sold.get(night, (0, Money.zero()))[1],
                )
                for night in nights_between(first, last)
            ]
            return Report(
                first=first,
                last=last,
                days=days,
                reservations_made=reports.reservations_made(start, end),
                invoices=reports.invoice_count(start, end),
                invoiced=reports.invoiced(start, end),
                cash=reports.cash(start, end),
                cancellations=reports.cancellations(start, end),
                no_shows=reports.no_shows(start, end),
                categories=reports.by_category(first, last),
                availability_day=availability_day,
                availability=self._availability(uow, availability_day),
                unpaid=uow.invoices.unpaid(),
                in_house_due=self._in_house_due(uow),
            )

    def _instant(self, day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=self._clock.hotel_tz).astimezone(UTC)

    @staticmethod
    def _availability(uow: UnitOfWork, day: date) -> list[CategoryAvailability]:
        """Per category: rooms in service, closed for maintenance and sold that night."""
        states = uow.maintenance.states_on(day)
        counts: dict[str, list[int]] = {}
        for room in uow.rooms.list():
            if not room.in_service:
                continue
            rooms, maintenance, sold = counts.setdefault(room.category_name, [0, 0, 0])
            state = states.get(room.id)
            counts[room.category_name] = [
                rooms + 1,
                maintenance + (state == "MAINTENANCE"),
                sold + (state in ("CONFIRMED", "CHECKED_IN")),
            ]
        return [CategoryAvailability(name, *c) for name, c in sorted(counts.items())]

    @staticmethod
    def _in_house_due(uow: UnitOfWork) -> Money:
        due = Money.zero()
        for reservation in uow.reservations.in_house():
            due += max(bill_for(uow, reservation).balance, Money.zero())
        return due

"""Check-out and invoices (story 4.7, business rule BR22)."""

from __future__ import annotations

from hotel.domain.actor import Actor
from hotel.domain.billing import Bill
from hotel.domain.clock import Clock
from hotel.domain.errors import NotFoundError, StaleDataError
from hotel.domain.invoices import Invoice, invoice_number
from hotel.domain.money import Money
from hotel.domain.paging import Page, PageRequest
from hotel.domain.reservations import Reservation
from hotel.domain.rooms import Housekeeping
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_staff
from hotel.services.billing import bill_for


def issue_invoice(uow: UnitOfWork, clock: Clock, actor: Actor, reservation: Reservation) -> Invoice:
    """Freeze the bill into an invoice, inside the caller's transaction.

    The number comes from the same transaction (counter table): if anything
    fails afterwards, the rollback also gives the number back, so the
    sequence has no gaps.
    """
    bill = bill_for(uow, reservation)
    now = clock.now()
    number = invoice_number(clock.today().year, uow.counters.next("invoice", clock.today().year))
    invoice = uow.invoices.add(
        Invoice(
            id=None,
            number=number,
            reservation_id=reservation.id,
            reservation_code=reservation.code,
            guest_name=reservation.guest_name,
            arrival=reservation.period.arrival,
            departure=reservation.period.departure,
            issued_at=now,
            lines=bill.lines,
            payments=bill.payments,
        ),
        actor.user_id,
    )
    record(
        uow,
        clock,
        actor,
        "invoice.issued",
        entity="invoice",
        entity_id=invoice.id,
        number=number,
        total=str(invoice.total),
    )
    return invoice


class InvoiceService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def preview_check_out(
        self, actor: Actor, reservation_id: int
    ) -> tuple[Reservation, Bill, bool]:
        """What checking out now would produce: (stay as it would end, its bill, early?).

        The check-out rule runs on a copy in memory; nothing is saved.
        """
        require_staff(actor)
        with self._uow() as uow:
            reservation = uow.reservations.get(reservation_id)
            if reservation is None:
                raise NotFoundError(entity="reservation", id=reservation_id)
            early = reservation.check_out(self._clock.now(), self._clock.today())
            return reservation, bill_for(uow, reservation), early

    def check_out(self, actor: Actor, reservation_id: int, *, version: int) -> Invoice:
        """Scenario §4.5: the guest leaves; the invoice is issued at the same moment."""
        require_staff(actor)
        with self._uow() as uow:
            reservation = uow.reservations.get(reservation_id)
            if reservation is None:
                raise NotFoundError(entity="reservation", id=reservation_id)
            if reservation.version != version:
                raise StaleDataError(entity="reservation", id=reservation_id)
            planned = reservation.period.departure
            early = reservation.check_out(self._clock.now(), self._clock.today())
            uow.reservations.update(reservation)
            if early:
                # The unused nights become available for other guests again.
                uow.reservations.release_nights(
                    reservation.id, from_night=reservation.period.departure
                )
            uow.rooms.set_housekeeping(
                [r.room_id for r in reservation.current_rooms], Housekeeping.DIRTY
            )
            record(
                uow,
                self._clock,
                actor,
                "reservation.checked_out",
                entity="reservation",
                entity_id=reservation.id,
                code=reservation.code,
                planned_departure=planned.isoformat(),
                departure=reservation.period.departure.isoformat(),
            )
            return issue_invoice(uow, self._clock, actor, reservation)

    # ------------------------------------------------------------ reading
    def get(self, actor: Actor, invoice_id: int) -> Invoice:
        require_staff(actor)
        with self._uow() as uow:
            invoice = uow.invoices.get(invoice_id)
        if invoice is None:
            raise NotFoundError(entity="invoice", id=invoice_id)
        return invoice

    def for_reservation(self, actor: Actor, reservation_id: int) -> Invoice | None:
        require_staff(actor)
        with self._uow() as uow:
            return uow.invoices.for_reservation(reservation_id)

    def search(self, actor: Actor, query: str, request: PageRequest) -> Page[Invoice]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.invoices.search(query, request)

    def unpaid(self, actor: Actor) -> list[tuple[int, str, str, Money]]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.invoices.unpaid()

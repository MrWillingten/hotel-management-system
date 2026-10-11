"""Availability and reservations."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.paging import Page, PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import (
    BookedRoom,
    CancellationPolicy,
    Reservation,
    RoomNight,
    RoomRequest,
    reservation_code,
    validate_room_requests,
    validate_stay,
)
from hotel.domain.rooms import Room
from hotel.persistence.repositories.reservations import ReservationFilter
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_staff

MAX_ALTERNATIVES = 5
MAX_NOTES = 500


class RoomUnavailableError(ConflictError):
    """Scenario §4.3: the room is taken on some of the requested nights."""

    code = "reservation.room_unavailable"

    def __init__(self, room: Room, nights: list[date], alternatives: list[Room]) -> None:
        super().__init__(
            room=room.number,
            first=nights[0].isoformat(),
            last=nights[-1].isoformat(),
            count=len(nights),
        )
        self.room = room
        self.nights = nights
        self.alternatives = alternatives


@dataclass(frozen=True, slots=True)
class QuoteLine:
    room: Room
    request: RoomRequest
    nights: list[RoomNight]

    @property
    def subtotal(self) -> Money:
        total = Money.zero()
        for night in self.nights:
            total += night.rate
        return total


@dataclass(frozen=True, slots=True)
class Quote:
    """What a booking will cost, computed exactly as the booking itself will be."""

    period: StayPeriod
    lines: list[QuoteLine] = field(default_factory=list)

    @property
    def total(self) -> Money:
        total = Money.zero()
        for line in self.lines:
            total += line.subtotal
        return total


def _clean_notes(notes: str) -> str:
    notes = unicodedata.normalize("NFC", notes).strip()
    if len(notes) > MAX_NOTES:
        raise ValidationError(
            "notes.invalid", fields={"notes": "notes.invalid"}, max_length=MAX_NOTES
        )
    return notes


class ReservationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        policy: CancellationPolicy | None = None,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self.policy = policy or CancellationPolicy()

    def free_cancellation_until(self, period: StayPeriod) -> datetime:
        """The last moment the guest can cancel without the fee."""
        return (
            self.policy.arrival_instant(period.arrival, self._clock.hotel_tz) - self.policy.window
        )

    # ------------------------------------------------------------ availability
    def find_available_rooms(
        self,
        actor: Actor,
        period: StayPeriod,
        *,
        min_capacity: int = 1,
        category_id: int | None = None,
    ) -> list[Room]:
        """Rooms in service and free on every night of `period` (half-open)."""
        require_staff(actor)
        validate_stay(period, self._clock.today())
        with self._uow() as uow:
            blocked = uow.reservations.blocked_nights(period)
            return [
                room
                for room in uow.rooms.list(category_id=category_id)
                if room.in_service and room.capacity >= min_capacity and room.id not in blocked
            ]

    # ------------------------------------------------------------ booking
    def quote(
        self, actor: Actor, *, guest_id: int, period: StayPeriod, rooms: list[RoomRequest]
    ) -> Quote:
        """Check a booking completely and price it, without saving anything."""
        require_staff(actor)
        validate_stay(period, self._clock.today())
        validate_room_requests(rooms)
        with self._uow() as uow:
            self._bookable_guest(uow, guest_id)
            return self._price(uow, period, self._check_rooms(uow, period, rooms))

    def create(
        self,
        actor: Actor,
        *,
        guest_id: int,
        period: StayPeriod,
        rooms: list[RoomRequest],
        notes: str = "",
    ) -> Reservation:
        """Book one or more rooms for a guest (business rules BR3-BR7, scenario §4.3)."""
        require_staff(actor)
        today = self._clock.today()
        validate_stay(period, today)
        validate_room_requests(rooms)
        notes = _clean_notes(notes)
        # One transaction holding the write lock (BEGIN IMMEDIATE): between the
        # availability check below and the insert, nobody else can book.
        with self._uow() as uow:
            self._bookable_guest(uow, guest_id)
            quote = self._price(uow, period, self._check_rooms(uow, period, rooms))
            sequence = uow.counters.next("reservation", today.year)
            reservation = Reservation(
                id=None,
                code=reservation_code(today.year, sequence),
                guest_id=guest_id,
                period=period,
                rooms=[
                    BookedRoom(line.room.id, line.request.adults, line.request.children)
                    for line in quote.lines
                ],
                nights=[night for line in quote.lines for night in line.nights],
                notes=notes,
                created_by=actor.user_id,
                created_at=self._clock.now(),
            )
            uow.reservations.add(reservation)
            record(
                uow,
                self._clock,
                actor,
                "reservation.created",
                entity="reservation",
                entity_id=reservation.id,
                code=reservation.code,
                rooms=len(rooms),
                nights=period.nights,
                total=str(quote.total),
            )
            return uow.reservations.get(reservation.id)

    # ------------------------------------------------------------ reading
    def get(self, actor: Actor, reservation_id: int) -> Reservation:
        require_staff(actor)
        with self._uow() as uow:
            return self._load(uow, reservation_id)

    def search(
        self, actor: Actor, filters: ReservationFilter, request: PageRequest
    ) -> Page[Reservation]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.reservations.search(filters, request)

    def for_guest(self, actor: Actor, guest_id: int) -> list[Reservation]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.reservations.for_guest(guest_id)

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _load(uow: UnitOfWork, reservation_id: int) -> Reservation:
        reservation = uow.reservations.get(reservation_id)
        if reservation is None:
            raise NotFoundError(entity="reservation", id=reservation_id)
        return reservation

    @staticmethod
    def _bookable_guest(uow: UnitOfWork, guest_id: int) -> None:
        guest = uow.guests.get(guest_id)
        if guest is None or not guest.is_active:
            raise NotFoundError(entity="guest", id=guest_id)
        if guest.do_not_rent:
            raise BusinessRuleViolation("reservation.guest_do_not_rent")

    def _check_rooms(
        self,
        uow: UnitOfWork,
        period: StayPeriod,
        requests: list[RoomRequest],
        *,
        exclude_reservation_id: int | None = None,
    ) -> list[tuple[Room, RoomRequest]]:
        blocked = uow.reservations.blocked_nights(
            period, exclude_reservation_id=exclude_reservation_id
        )
        checked = []
        for request in requests:
            room = uow.rooms.get(request.room_id)
            if room is None:
                raise NotFoundError(entity="room", id=request.room_id)
            if not room.in_service:
                raise ConflictError("reservation.room_out_of_service", room=room.number)
            if not room.can_host(request.occupants):  # business rule BR7
                raise BusinessRuleViolation(
                    "reservation.capacity_exceeded",
                    room=room.number,
                    capacity=room.capacity,
                    occupants=request.occupants,
                )
            if room.id in blocked:  # business rules BR3, BR5, BR6
                taken = {r.room_id for r in requests}
                raise RoomUnavailableError(
                    room,
                    blocked[room.id],
                    self._alternatives(uow, room, request.occupants, blocked, taken),
                )
            checked.append((room, request))
        return checked

    @staticmethod
    def _alternatives(
        uow: UnitOfWork, wanted: Room, occupants: int, blocked: dict, taken: set[int]
    ) -> list[Room]:
        """Free rooms that fit, the same category first, then the closest price."""
        candidates = [
            room
            for room in uow.rooms.list()
            if room.in_service
            and room.capacity >= occupants
            and room.id not in blocked
            and room.id not in taken
        ]
        candidates.sort(
            key=lambda r: (
                r.category_id != wanted.category_id,
                abs(r.nightly_rate.millimes - wanted.nightly_rate.millimes),
                r.number,
            )
        )
        return candidates[:MAX_ALTERNATIVES]

    def _price(
        self, uow: UnitOfWork, period: StayPeriod, rooms: list[tuple[Room, RoomRequest]]
    ) -> Quote:
        lines = [
            QuoteLine(
                room,
                request,
                [
                    RoomNight(room.id, night, self._rate_for(room, night))
                    for night in period.each_night()
                ],
            )
            for room, request in rooms
        ]
        return Quote(period, lines)

    @staticmethod
    def _rate_for(room: Room, night: date) -> Money:
        """Today one rate per room; seasonal rates (Sprint 5) only change this method."""
        return room.nightly_rate

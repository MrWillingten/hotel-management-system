"""Availability and reservations."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.paging import Page, PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.pricing import Pricing
from hotel.domain.reservations import (
    MAX_NIGHTS,
    BookedRoom,
    CancellationPolicy,
    Reservation,
    ReservationStatus,
    RoomNight,
    RoomRequest,
    reservation_code,
    validate_room_requests,
    validate_stay,
)
from hotel.domain.rooms import Housekeeping, Room
from hotel.persistence.repositories.reservations import ReservationFilter
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role, require_staff
from hotel.services.hotel_settings import load_settings
from hotel.services.invoices import issue_invoice

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


@dataclass(frozen=True, slots=True)
class CalendarCell:
    night: date
    kind: str  # FREE, RESERVED, OCCUPIED, MAINTENANCE, OUT_OF_SERVICE, PAST
    reservation_id: int | None = None
    code: str | None = None
    guest_name: str | None = None
    starts_here: bool = False  # first night shown for this reservation


@dataclass(frozen=True, slots=True)
class CalendarRow:
    room: Room
    cells: list[CalendarCell]


@dataclass(frozen=True, slots=True)
class Calendar:
    start: date
    days: list[date]
    rows: list[CalendarRow]
    today: date


class ReservationService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    @staticmethod
    def _policy(uow: UnitOfWork) -> CancellationPolicy:
        """BR11 with the hotel's current settings (fee, window, check-in time)."""
        return load_settings(uow).cancellation_policy()

    def free_cancellation_until(self, period: StayPeriod) -> datetime:
        """The last moment the guest can cancel without the fee."""
        with self._uow() as uow:
            policy = self._policy(uow)
        return policy.arrival_instant(period.arrival, self._clock.hotel_tz) - policy.window

    def arrival_has_passed(self, period: StayPeriod) -> bool:
        """True once the check-in time of the arrival day is over (no-show possible)."""
        with self._uow() as uow:
            policy = self._policy(uow)
        return self._clock.now() >= policy.arrival_instant(period.arrival, self._clock.hotel_tz)

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

    # ------------------------------------------------------------ changing
    def preview_change(
        self,
        actor: Actor,
        reservation_id: int,
        *,
        period: StayPeriod,
        rooms: list[RoomRequest],
    ) -> tuple[Reservation, Quote]:
        """Check a change completely and return (current reservation, new price)."""
        require_staff(actor)
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            return reservation, self._plan_change(uow, reservation, period, rooms)

    def modify(
        self,
        actor: Actor,
        reservation_id: int,
        *,
        version: int,
        period: StayPeriod,
        rooms: list[RoomRequest],
    ) -> Reservation:
        """Scenario §4.4: change dates, rooms or occupants when availability permits.

        Nights that stay the same keep the price locked when they were booked;
        added nights are priced at today's rate.
        """
        require_staff(actor)
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            if reservation.version != version:
                raise StaleDataError(entity="reservation", id=reservation_id)
            before_period, before_total = reservation.period, reservation.accommodation_total
            quote = self._plan_change(uow, reservation, period, rooms)
            reservation.period = period
            moved_out = {r.room_id: r.moved_out_on for r in reservation.rooms}
            reservation.rooms = [
                BookedRoom(
                    line.room.id,
                    line.request.adults,
                    line.request.children,
                    moved_out_on=moved_out.get(line.room.id),
                )
                for line in quote.lines
            ]
            reservation.nights = [night for line in quote.lines for night in line.nights]
            uow.reservations.update(reservation)
            uow.reservations.replace_rooms_and_nights(reservation)
            record(
                uow,
                self._clock,
                actor,
                "reservation.modified",
                entity="reservation",
                entity_id=reservation.id,
                before=f"{before_period.arrival}/{before_period.departure}",
                after=f"{period.arrival}/{period.departure}",
                total_before=str(before_total),
                total_after=str(quote.total),
            )
            return uow.reservations.get(reservation.id)

    def _plan_change(
        self,
        uow: UnitOfWork,
        reservation: Reservation,
        period: StayPeriod,
        rooms: list[RoomRequest],
    ) -> Quote:
        today = self._clock.today()
        validate_room_requests(rooms)
        check_period = period
        if reservation.status is ReservationStatus.CHECKED_IN:
            # The guest is in the house: only the departure (and who sleeps where
            # in the same rooms) can change. Moving rooms is a separate operation.
            current = {r.room_id for r in reservation.current_rooms}
            if (
                period.arrival != reservation.period.arrival
                or {r.room_id for r in rooms} != current
            ):
                raise BusinessRuleViolation("reservation.checked_in_limits")
            if period.departure <= today:
                raise ValidationError(
                    "reservation.departure_in_past",
                    fields={"departure": "reservation.departure_in_past"},
                )
            if period.nights > MAX_NIGHTS:
                raise ValidationError("reservation.too_long", max=MAX_NIGHTS)
            # Nights already spent are history: only tonight onwards must be free.
            check_period = StayPeriod(max(today, period.arrival), period.departure)
        elif reservation.status is ReservationStatus.CONFIRMED:
            validate_stay(period, today)
        else:
            raise InvalidStateTransitionError(
                "reservation.not_modifiable", current=reservation.status.value
            )
        checked = self._check_rooms(uow, check_period, rooms, exclude_reservation_id=reservation.id)
        locked = {(n.room_id, n.night): n.rate for n in reservation.nights}
        pricing = self._pricing(uow)
        # A night that was already booked keeps its price; a new night costs today's.
        # Before the check period, only nights the room really held are kept (after
        # a move, the new room has no nights before the move).
        lines = [
            QuoteLine(
                room,
                request,
                [
                    RoomNight(
                        room.id,
                        night,
                        locked[(room.id, night)]
                        if (room.id, night) in locked
                        else pricing.rate_for(room, night),
                    )
                    for night in period.each_night()
                    if night >= check_period.arrival or (room.id, night) in locked
                ],
            )
            for room, request in checked
        ]
        # Rooms the guest moved out of keep their nights on the bill (story 6.5).
        for booked in reservation.rooms:
            if not booked.is_current:
                lines.append(
                    QuoteLine(
                        uow.rooms.get(booked.room_id),
                        RoomRequest(booked.room_id, booked.adults, booked.children),
                        reservation.nights_of(booked.room_id),
                    )
                )
        return Quote(period, lines)

    # ------------------------------------------------------------ moving rooms
    def move_candidates(self, actor: Actor, reservation_id: int, from_room_id: int) -> list[Room]:
        """Rooms the guests of `from_room_id` could move to, closest first.

        Free from tonight (or the arrival) to the departure, big enough, in
        service and not already part of the stay; the same category comes
        first, then the closest price.
        """
        require_staff(actor)
        today = self._clock.today()
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            booked = next((r for r in reservation.current_rooms if r.room_id == from_room_id), None)
            first = max(today, reservation.period.arrival)
            if booked is None or first >= reservation.period.departure:
                return []
            blocked = uow.reservations.blocked_nights(
                StayPeriod(first, reservation.period.departure)
            )
            used = {r.room_id for r in reservation.rooms}
            current = uow.rooms.get(from_room_id)
            candidates = [
                room
                for room in uow.rooms.list()
                if room.in_service
                and room.capacity >= booked.occupants
                and room.id not in blocked
                and room.id not in used
            ]
            return sorted(
                candidates,
                key=lambda room: (
                    room.category_id != current.category_id,
                    abs(room.nightly_rate.millimes - current.nightly_rate.millimes),
                    room.number,
                ),
            )

    def move_room(
        self,
        actor: Actor,
        reservation_id: int,
        *,
        version: int,
        from_room_id: int,
        to_room_id: int,
        charge_new_rate: bool = False,
    ) -> Reservation:
        """Story 6.5: move the guests of one room to another, from tonight on.

        By default each night keeps its locked price (the hotel's courtesy, e.g.
        after a broken air conditioner). Only a manager may charge the new
        room's price instead (an upgrade the guest asked for). The new room is
        checked exactly like a booking: in service, big enough, free.
        """
        require_staff(actor)
        if charge_new_rate:
            require_role(actor, Role.MANAGER)
        today = self._clock.today()
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            if reservation.version != version:
                raise StaleDataError(entity="reservation", id=reservation_id)
            old = next((r for r in reservation.current_rooms if r.room_id == from_room_id), None)
            to_room = uow.rooms.get(to_room_id)
            if to_room is None:
                raise NotFoundError(entity="room", id=to_room_id)
            before_total = reservation.accommodation_total
            pricing = self._pricing(uow)
            moved = reservation.move_room(
                from_room_id,
                to_room_id,
                today=today,
                number=to_room.number,
                category_name=to_room.category_name or "",
                rate_for=(lambda night: pricing.rate_for(to_room, night))
                if charge_new_rate
                else None,
            )
            self._check_rooms(
                uow,
                StayPeriod(moved[0], moved[-1] + timedelta(days=1)),
                [RoomRequest(to_room_id, old.adults, old.children)],
                exclude_reservation_id=reservation.id,
            )
            uow.reservations.update(reservation)
            uow.reservations.replace_rooms_and_nights(reservation)
            if reservation.status is ReservationStatus.CHECKED_IN:
                # The guests used the old room: it must be cleaned before anyone else.
                uow.rooms.set_housekeeping([from_room_id], Housekeeping.DIRTY)
            from_number = uow.rooms.get(from_room_id).number
            record(
                uow,
                self._clock,
                actor,
                "reservation.room_moved",
                entity="reservation",
                entity_id=reservation.id,
                from_room=from_number,
                to_room=to_room.number,
                nights=len(moved),
                price="new_rate" if charge_new_rate else "kept",
                total_before=str(before_total),
                total_after=str(reservation.accommodation_total),
            )
            return uow.reservations.get(reservation.id)

    # ------------------------------------------------------------ cancelling
    def cancellation_fee(self, actor: Actor, reservation_id: int) -> Money:
        """What cancelling now would cost (raises if it is no longer possible)."""
        require_staff(actor)
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            self._ensure_cancellable(reservation)
            return self._policy(uow).fee_for(reservation, self._clock.now(), self._clock.hotel_tz)

    def cancel(self, actor: Actor, reservation_id: int, *, version: int) -> Reservation:
        """Business rule BR11. The rooms are released immediately."""
        require_staff(actor)
        now = self._clock.now()
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            if reservation.version != version:
                raise StaleDataError(entity="reservation", id=reservation_id)
            self._ensure_cancellable(reservation)
            fee = self._policy(uow).fee_for(reservation, now, self._clock.hotel_tz)
            reservation.transition(ReservationStatus.CANCELLED)
            reservation.cancellation_fee = fee
            reservation.cancelled_at = now
            uow.reservations.update(reservation)
            uow.reservations.release_nights(reservation.id)
            record(
                uow,
                self._clock,
                actor,
                "reservation.cancelled",
                entity="reservation",
                entity_id=reservation.id,
                fee=str(fee),
                total=str(reservation.accommodation_total),
            )
            if not fee.is_zero():
                issue_invoice(uow, self._clock, actor, reservation)  # the fee is billed
            return uow.reservations.get(reservation.id)

    # ------------------------------------------------------------ front desk
    def check_in(self, actor: Actor, reservation_id: int, *, version: int) -> Reservation:
        """Scenario §4.5, business rule BR17: the guest has arrived."""
        require_staff(actor)
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            if reservation.version != version:
                raise StaleDataError(entity="reservation", id=reservation_id)
            reservation.check_in(self._clock.now(), self._clock.today())
            # The previous guest of a room may leave late on our arrival day:
            # nobody moves in before they have checked out.
            in_house = uow.reservations.in_house_rooms()
            for room in reservation.rooms:
                if room.room_id in in_house and in_house[room.room_id] != reservation.code:
                    raise BusinessRuleViolation(
                        "reservation.room_still_occupied",
                        room=room.number,
                        code=in_house[room.room_id],
                    )
            uow.reservations.update(reservation)
            record(
                uow,
                self._clock,
                actor,
                "reservation.checked_in",
                entity="reservation",
                entity_id=reservation.id,
                code=reservation.code,
            )
            return uow.reservations.get(reservation.id)

    def no_show_fee(self, actor: Actor, reservation_id: int) -> Money:
        """What recording a no-show now would charge (raises if not possible yet)."""
        require_staff(actor)
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            reservation.ensure_can_become(ReservationStatus.NO_SHOW)
            return self._policy(uow).no_show_fee(
                reservation, self._clock.now(), self._clock.hotel_tz
            )

    def record_no_show(self, actor: Actor, reservation_id: int, *, version: int) -> Reservation:
        """Decision F: the guest never came. Charged like a late cancellation."""
        require_staff(actor)
        now = self._clock.now()
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            if reservation.version != version:
                raise StaleDataError(entity="reservation", id=reservation_id)
            reservation.ensure_can_become(ReservationStatus.NO_SHOW)
            fee = self._policy(uow).no_show_fee(reservation, now, self._clock.hotel_tz)
            reservation.transition(ReservationStatus.NO_SHOW)
            reservation.cancellation_fee = fee
            reservation.no_show_at = now
            uow.reservations.update(reservation)
            # The remaining nights can be sold again to walk-in guests.
            uow.reservations.release_nights(reservation.id)
            record(
                uow,
                self._clock,
                actor,
                "reservation.no_show",
                entity="reservation",
                entity_id=reservation.id,
                fee=str(fee),
                total=str(reservation.accommodation_total),
            )
            if not fee.is_zero():
                issue_invoice(uow, self._clock, actor, reservation)
            return uow.reservations.get(reservation.id)

    @staticmethod
    def _ensure_cancellable(reservation: Reservation) -> None:
        if reservation.status is not ReservationStatus.CONFIRMED:
            raise InvalidStateTransitionError(
                "reservation.not_cancellable", current=reservation.status.value
            )

    # ------------------------------------------------------------ availability grid
    def calendar(self, actor: Actor, start: date, *, days: int = 14) -> Calendar:
        """Rooms x days: what every room is doing on every night (story 3.4)."""
        require_staff(actor)
        days = max(1, min(days, 31))
        period = StayPeriod(start, start + timedelta(days=days))
        today = self._clock.today()
        with self._uow() as uow:
            taken = {(b.room_id, b.night): b for b in uow.reservations.calendar(period)}
            rooms = uow.rooms.list()
        nights = list(period.each_night())
        rows = []
        for room in rooms:
            cells = []
            previous = None
            for night in nights:
                blocked = taken.get((room.id, night))
                if blocked is not None and blocked.maintenance_id is not None:
                    cell = CalendarCell(night, "MAINTENANCE")
                elif blocked is not None:
                    kind = "OCCUPIED" if blocked.status == "CHECKED_IN" else "RESERVED"
                    cell = CalendarCell(
                        night,
                        kind,
                        blocked.reservation_id,
                        blocked.code,
                        blocked.guest_name,
                        starts_here=previous != blocked.reservation_id,
                    )
                elif not room.in_service:
                    cell = CalendarCell(night, "OUT_OF_SERVICE")
                else:
                    cell = CalendarCell(night, "PAST" if night < today else "FREE")
                previous = cell.reservation_id
                cells.append(cell)
            rows.append(CalendarRow(room, cells))
        return Calendar(start, nights, rows, today)

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
        if guest.is_anonymised:
            raise BusinessRuleViolation("guest.anonymised")
        if guest.is_archived:
            raise BusinessRuleViolation("guest.archived")

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
        pricing = self._pricing(uow)
        lines = [
            QuoteLine(
                room,
                request,
                [
                    RoomNight(room.id, night, pricing.rate_for(room, night))
                    for night in period.each_night()
                ],
            )
            for room, request in rooms
        ]
        return Quote(period, lines)

    @staticmethod
    def _pricing(uow: UnitOfWork) -> Pricing:
        """Story 5.6: rate periods and the weekend rule, read in the caller's transaction.

        A night that was already booked keeps its locked price (BR20); only new
        nights are priced with this.
        """
        settings = load_settings(uow)
        return Pricing(
            periods=tuple(uow.rate_periods.list()),
            weekend_nights=settings.weekend_days,
            weekend_surcharge_bp=settings.weekend_surcharge_bp,
        )

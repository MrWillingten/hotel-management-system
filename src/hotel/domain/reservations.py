"""Reservations, their life cycle and the cancellation policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, tzinfo
from enum import StrEnum

from hotel.domain.errors import (
    BusinessRuleViolation,
    InvalidStateTransitionError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod

MAX_NIGHTS = 60
BOOKING_HORIZON = timedelta(days=730)  # bookings at most two years ahead
MAX_ROOMS_PER_RESERVATION = 10


class ReservationStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

    @property
    def is_active(self) -> bool:
        """Active reservations hold their rooms (business rule BR3)."""
        return self in (ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN)


# The only allowed moves through the life cycle; everything else is refused.
ALLOWED_TRANSITIONS: dict[ReservationStatus, frozenset[ReservationStatus]] = {
    ReservationStatus.CONFIRMED: frozenset(
        {ReservationStatus.CHECKED_IN, ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW}
    ),
    ReservationStatus.CHECKED_IN: frozenset({ReservationStatus.CHECKED_OUT}),
    ReservationStatus.CHECKED_OUT: frozenset(),
    ReservationStatus.CANCELLED: frozenset(),
    ReservationStatus.NO_SHOW: frozenset(),
}


@dataclass(frozen=True, slots=True)
class RoomRequest:
    """One room the guest asks for, with who will sleep in it."""

    room_id: int
    adults: int
    children: int = 0

    @property
    def occupants(self) -> int:
        return self.adults + self.children


@dataclass(frozen=True, slots=True)
class BookedRoom:
    room_id: int
    adults: int
    children: int = 0
    number: str = ""  # filled when read, for display
    category_name: str = ""
    # Set when the guest moved to another room (story 6.5): the first night
    # no longer spent here. The room stays listed because its nights are billed.
    moved_out_on: date | None = None

    @property
    def is_current(self) -> bool:
        return self.moved_out_on is None

    @property
    def occupants(self) -> int:
        return self.adults + self.children


@dataclass(frozen=True, slots=True)
class RoomNight:
    """One room for one night, at the price locked when it was booked."""

    room_id: int
    night: date
    rate: Money


def validate_stay(period: StayPeriod, today: date) -> StayPeriod:
    if period.arrival < today:
        raise ValidationError(
            "reservation.arrival_in_past", fields={"arrival": "reservation.arrival_in_past"}
        )
    if period.nights > MAX_NIGHTS:
        raise ValidationError(
            "reservation.too_long", fields={"departure": "reservation.too_long"}, max=MAX_NIGHTS
        )
    if period.arrival > today + BOOKING_HORIZON:
        raise ValidationError("reservation.too_far", fields={"arrival": "reservation.too_far"})
    return period


def validate_room_requests(requests: list[RoomRequest]) -> list[RoomRequest]:
    if not 1 <= len(requests) <= MAX_ROOMS_PER_RESERVATION:
        raise ValidationError("reservation.rooms_count", max=MAX_ROOMS_PER_RESERVATION)
    if len({r.room_id for r in requests}) != len(requests):
        raise ValidationError("reservation.room_twice")
    for request in requests:
        if request.adults < 1 or request.children < 0:
            raise ValidationError("reservation.occupants_invalid")
    return requests


def reservation_code(year: int, sequence: int) -> str:
    return f"R-{year}-{sequence:05d}"


@dataclass(slots=True)
class Reservation:
    id: int | None
    code: str
    guest_id: int
    period: StayPeriod
    status: ReservationStatus = ReservationStatus.CONFIRMED
    rooms: list[BookedRoom] = field(default_factory=list)
    nights: list[RoomNight] = field(default_factory=list)
    cancellation_fee: Money | None = None
    notes: str = ""
    created_by: int | None = None
    created_at: datetime | None = None
    cancelled_at: datetime | None = None
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    no_show_at: datetime | None = None
    version: int = 1
    guest_name: str = ""  # filled when read, for display

    @property
    def accommodation_total(self) -> Money:
        """Business rule BR8: the sum of every booked night at its locked price."""
        total = Money.zero()
        for night in self.nights:
            total += night.rate
        return total

    @property
    def current_rooms(self) -> list[BookedRoom]:
        """The rooms the guests use now (rooms they moved out of are left out)."""
        return [room for room in self.rooms if room.is_current]

    @property
    def occupants(self) -> int:
        return sum(room.occupants for room in self.current_rooms)

    def nights_of(self, room_id: int) -> list[RoomNight]:
        return [n for n in self.nights if n.room_id == room_id]

    def ensure_can_become(self, to: ReservationStatus) -> None:
        if to not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStateTransitionError(
                "reservation.invalid_transition", current=self.status.value, requested=to.value
            )

    def transition(self, to: ReservationStatus) -> None:
        self.ensure_can_become(to)
        self.status = to

    def check_in(self, now: datetime, today: date) -> None:
        """Business rule BR17: on the arrival day, or later during the stay.

        A guest who arrives a day late keeps the booking (the missed night is
        still charged); checking in before the arrival day is refused because
        the room may still belong to someone else tonight.
        """
        self.ensure_can_become(ReservationStatus.CHECKED_IN)
        if today < self.period.arrival:
            raise BusinessRuleViolation(
                "reservation.check_in_too_early", arrival=self.period.arrival.isoformat()
            )
        if today >= self.period.departure:
            raise BusinessRuleViolation("reservation.check_in_too_late")
        self.transition(ReservationStatus.CHECKED_IN)
        self.checked_in_at = now

    def check_out(self, now: datetime, today: date) -> bool:
        """The guest leaves. Returns True for an early departure.

        Decision F: only the nights actually stayed are charged, so the nights
        from today on are dropped (and released by the caller). A guest who
        leaves on the arrival day still pays the first night.
        """
        self.ensure_can_become(ReservationStatus.CHECKED_OUT)
        departure = max(today, self.period.arrival + timedelta(days=1))
        early = departure < self.period.departure
        if early:
            self.period = StayPeriod(self.period.arrival, departure)
            self.nights = [n for n in self.nights if n.night < departure]
        self.transition(ReservationStatus.CHECKED_OUT)
        self.checked_out_at = now
        return early

    def move_room(
        self,
        from_room_id: int,
        to_room_id: int,
        *,
        today: date,
        number: str = "",
        category_name: str = "",
        rate_for: Callable[[date], Money] | None = None,
    ) -> list[date]:
        """Story 6.5: the nights from today on move to another room.

        Nights already spent stay where they were (and stay on the bill); the
        same people sleep in the new room. Each moved night keeps its locked
        price (a courtesy move) unless `rate_for` gives the new room's price
        (an upgrade the guest pays for). Returns the nights that moved; the
        caller checks the new room is free on them.
        """
        if self.status not in (ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN):
            raise InvalidStateTransitionError(
                "reservation.not_modifiable", current=self.status.value
            )
        booked = next((r for r in self.current_rooms if r.room_id == from_room_id), None)
        if booked is None:
            raise ValidationError("reservation.move_unknown_room")
        if any(r.room_id == to_room_id for r in self.rooms):
            # Also a room left earlier: one line per room keeps the bill readable.
            raise BusinessRuleViolation("reservation.move_room_already_used")
        moving = [n for n in self.nights_of(from_room_id) if n.night >= today]
        if not moving:
            raise BusinessRuleViolation("reservation.move_nothing_left")
        stayed = len(self.nights_of(from_room_id)) > len(moving)
        moved_nights = {n.night for n in moving}
        self.nights = [
            n for n in self.nights if not (n.room_id == from_room_id and n.night in moved_nights)
        ] + [
            RoomNight(to_room_id, n.night, rate_for(n.night) if rate_for else n.rate)
            for n in moving
        ]
        new_room = BookedRoom(to_room_id, booked.adults, booked.children, number, category_name)
        position = self.rooms.index(booked)
        if stayed:
            self.rooms[position] = replace(booked, moved_out_on=moving[0].night)
            self.rooms.append(new_room)
        else:  # not a night spent there yet: the old room simply disappears
            self.rooms[position] = new_room
        return [n.night for n in moving]


@dataclass(frozen=True, slots=True)
class CancellationPolicy:
    """Business rule BR11: 20 % of accommodation if cancelled less than 48 h before arrival.

    "Arrival" means the arrival day at the hotel's check-in time (14:00 by
    default), in the hotel's time zone. Cancelling exactly 48:00 before is free:
    the rule says *less than* 48 hours. Cancelling once the arrival time has
    passed is not a cancellation any more: it is a no-show.
    """

    fee_basis_points: int = 2_000
    window: timedelta = timedelta(hours=48)
    check_in_time: time = time(14, 0)
    grace_period: timedelta = timedelta(0)  # optional free change-of-mind after booking

    def arrival_instant(self, arrival: date, tz: tzinfo) -> datetime:
        return datetime.combine(arrival, self.check_in_time, tzinfo=tz)

    def free_until(self, reservation: Reservation, tz: tzinfo) -> datetime:
        return self.arrival_instant(reservation.period.arrival, tz) - self.window

    def fee_for(self, reservation: Reservation, now: datetime, tz: tzinfo) -> Money:
        arrival = self.arrival_instant(reservation.period.arrival, tz)
        if now >= arrival:
            raise BusinessRuleViolation("reservation.cancel_after_arrival")
        within_grace = (
            reservation.created_at is not None and now - reservation.created_at < self.grace_period
        )
        if arrival - now < self.window and not within_grace:
            return reservation.accommodation_total.percent(self.fee_basis_points)
        return Money.zero()

    def no_show_fee(self, reservation: Reservation, now: datetime, tz: tzinfo) -> Money:
        """Decision F: a no-show is charged like a late cancellation.

        It can only be recorded once the arrival time has passed; before that
        the guest may still come (or cancel).
        """
        if now < self.arrival_instant(reservation.period.arrival, tz):
            raise BusinessRuleViolation(
                "reservation.no_show_too_early", arrival=reservation.period.arrival.isoformat()
            )
        return reservation.accommodation_total.percent(self.fee_basis_points)

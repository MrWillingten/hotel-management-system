"""Room categories, rooms and maintenance (managers change; all staff consult)."""

from __future__ import annotations

from datetime import date

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import ConflictError, NotFoundError, StaleDataError, ValidationError
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.rooms import (
    MAX_MAINTENANCE_NIGHTS,
    Housekeeping,
    MaintenancePeriod,
    Room,
    RoomCategory,
    RoomOverview,
    RoomStatus,
    validate_capacity,
    validate_category_name,
    validate_nightly_rate,
    validate_room_number,
    validate_text,
)
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role, require_staff


class RoomService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    # ------------------------------------------------------------ categories
    def list_categories(self, actor: Actor) -> list[RoomCategory]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.categories.list_all()

    def create_category(self, actor: Actor, *, name: str, description: str = "") -> RoomCategory:
        require_role(actor, Role.MANAGER)
        name = validate_category_name(name)
        description = validate_text(description, "description", max_length=300)
        with self._uow() as uow:
            if uow.categories.name_taken(name):
                raise ConflictError("category.name_taken", fields={"name": "category.name_taken"})
            category = uow.categories.add(RoomCategory(None, name, description))
            record(
                uow,
                self._clock,
                actor,
                "room.category_created",
                entity="room_category",
                entity_id=category.id,
            )
            return category

    def update_category(
        self, actor: Actor, category_id: int, *, version: int, name: str, description: str
    ) -> RoomCategory:
        require_role(actor, Role.MANAGER)
        name = validate_category_name(name)
        description = validate_text(description, "description", max_length=300)
        with self._uow() as uow:
            category = uow.categories.get(category_id)
            if category is None:
                raise NotFoundError(entity="room_category", id=category_id)
            if category.version != version:
                raise StaleDataError(entity="room_category", id=category_id)
            if uow.categories.name_taken(name, except_id=category_id):
                raise ConflictError("category.name_taken", fields={"name": "category.name_taken"})
            category.name, category.description = name, description
            uow.categories.update(category)
            record(
                uow,
                self._clock,
                actor,
                "room.category_updated",
                entity="room_category",
                entity_id=category.id,
            )
            return category

    # ------------------------------------------------------------ rooms
    def list_rooms(self, actor: Actor, *, category_id: int | None = None) -> list[RoomOverview]:
        """Every room with what it is doing tonight."""
        require_staff(actor)
        with self._uow() as uow:
            states = self._states(uow)
            return [
                RoomOverview(room, self._status(room, states))
                for room in uow.rooms.list(category_id=category_id)
            ]

    def get_room(self, actor: Actor, room_id: int) -> RoomOverview:
        require_staff(actor)
        with self._uow() as uow:
            room = self._load(uow, room_id)
            return RoomOverview(room, self._status(room, self._states(uow)))

    def set_housekeeping(self, actor: Actor, room_id: int, state: Housekeeping) -> Room:
        """Story 4.9: any staff member can mark a room clean (or to clean)."""
        require_staff(actor)
        with self._uow() as uow:
            room = self._load(uow, room_id)
            uow.rooms.set_housekeeping([room.id], state)
            record(
                uow,
                self._clock,
                actor,
                "room.housekeeping",
                entity="room",
                entity_id=room.id,
                state=state.value,
            )
            room.housekeeping = state
            return room

    def create_room(
        self,
        actor: Actor,
        *,
        number: str,
        category_id: int,
        capacity: int,
        nightly_rate: Money,
        notes: str = "",
    ) -> Room:
        require_role(actor, Role.MANAGER)
        room = Room(
            id=None,
            number=validate_room_number(number),
            category_id=category_id,
            capacity=validate_capacity(capacity),
            nightly_rate=validate_nightly_rate(nightly_rate),
            notes=validate_text(notes, "notes", max_length=500),
        )
        with self._uow() as uow:
            self._check_room(uow, room)
            room = uow.rooms.add(room)
            record(
                uow,
                self._clock,
                actor,
                "room.created",
                entity="room",
                entity_id=room.id,
                number=room.number,
            )
            return uow.rooms.get(room.id)

    def update_room(
        self,
        actor: Actor,
        room_id: int,
        *,
        version: int,
        number: str,
        category_id: int,
        capacity: int,
        nightly_rate: Money,
        in_service: bool,
        notes: str = "",
    ) -> Room:
        """Changing the rate never affects existing bookings: prices are locked per night."""
        require_role(actor, Role.MANAGER)
        number = validate_room_number(number)
        capacity = validate_capacity(capacity)
        nightly_rate = validate_nightly_rate(nightly_rate)
        notes = validate_text(notes, "notes", max_length=500)
        with self._uow() as uow:
            room = self._load(uow, room_id)
            if room.version != version:
                raise StaleDataError(entity="room", id=room_id)
            before = (
                room.number,
                room.category_id,
                room.capacity,
                room.nightly_rate,
                room.in_service,
                room.notes,
            )
            room.number, room.category_id, room.capacity = number, category_id, capacity
            room.nightly_rate, room.in_service, room.notes = nightly_rate, in_service, notes
            self._check_room(uow, room)
            self._protect_future_bookings(uow, room)
            uow.rooms.update(room)
            names = ("number", "category", "capacity", "nightly_rate", "in_service", "notes")
            after = (number, category_id, capacity, nightly_rate, in_service, notes)
            changed = [n for n, old, new in zip(names, before, after, strict=True) if old != new]
            record(
                uow,
                self._clock,
                actor,
                "room.updated",
                entity="room",
                entity_id=room.id,
                fields=changed,
            )
            return uow.rooms.get(room.id)

    # ------------------------------------------------------------ maintenance
    def maintenance_for_room(self, actor: Actor, room_id: int) -> list[MaintenancePeriod]:
        require_staff(actor)
        with self._uow() as uow:
            self._load(uow, room_id)
            return uow.maintenance.list_for_room(room_id)

    def schedule_maintenance(
        self, actor: Actor, room_id: int, *, first_night: date, reopens_on: date, reason: str
    ) -> MaintenancePeriod:
        """Close a room from `first_night` until it reopens on `reopens_on` (scenario §4.1)."""
        require_role(actor, Role.MANAGER)
        reason = validate_text(reason, "reason", max_length=200, required=True)
        if reopens_on <= first_night:
            raise ValidationError(
                "maintenance.reopen_not_after_start",
                fields={"reopens_on": "maintenance.reopen_not_after_start"},
            )
        period = StayPeriod(first_night, reopens_on)
        if first_night < self._clock.today():
            raise ValidationError(
                "maintenance.in_past", fields={"first_night": "maintenance.in_past"}
            )
        if period.nights > MAX_MAINTENANCE_NIGHTS:
            raise ValidationError(
                "maintenance.too_long",
                fields={"reopens_on": "maintenance.too_long"},
                max=MAX_MAINTENANCE_NIGHTS,
            )
        with self._uow() as uow:
            self._load(uow, room_id)
            clashes = uow.maintenance.blocked_nights(room_id, period)
            if clashes:
                raise ConflictError(
                    "maintenance.conflict",
                    first=clashes[0].isoformat(),
                    last=clashes[-1].isoformat(),
                    count=len(clashes),
                )
            maintenance = uow.maintenance.add(
                MaintenancePeriod(None, room_id, period, reason, actor.user_id, self._clock.now())
            )
            record(
                uow,
                self._clock,
                actor,
                "room.maintenance_scheduled",
                entity="room",
                entity_id=room_id,
                maintenance_id=maintenance.id,
                first_night=first_night.isoformat(),
                reopens_on=reopens_on.isoformat(),
            )
            return maintenance

    def cancel_maintenance(self, actor: Actor, maintenance_id: int) -> MaintenancePeriod | None:
        """Delete a future period, or end an ongoing one today. Past periods stay as history."""
        require_role(actor, Role.MANAGER)
        today = self._clock.today()
        with self._uow() as uow:
            maintenance = uow.maintenance.get(maintenance_id)
            if maintenance is None:
                raise NotFoundError(entity="maintenance", id=maintenance_id)
            if maintenance.reopens_on <= today:
                raise ValidationError("maintenance.already_over")
            if maintenance.first_night >= today:
                uow.maintenance.delete(maintenance_id)
                action, result = "room.maintenance_cancelled", None
            else:
                uow.maintenance.end_early(maintenance_id, today)
                action, result = "room.maintenance_ended", uow.maintenance.get(maintenance_id)
            record(
                uow,
                self._clock,
                actor,
                action,
                entity="room",
                entity_id=maintenance.room_id,
                maintenance_id=maintenance_id,
            )
            return result

    # ------------------------------------------------------------ helpers
    def _states(self, uow: UnitOfWork) -> dict[int, str]:
        states = uow.maintenance.states_on(self._clock.today())
        # A guest still in the room on their departure day holds no night any
        # more, but the room is certainly not free until they check out.
        for room_id in uow.reservations.in_house_rooms():
            if states.get(room_id) != "MAINTENANCE":
                states[room_id] = "CHECKED_IN"
        return states

    @staticmethod
    def _status(room: Room, states: dict[int, str]) -> RoomStatus:
        if not room.in_service:
            return RoomStatus.OUT_OF_SERVICE
        state = states.get(room.id)
        if state == "MAINTENANCE":
            return RoomStatus.MAINTENANCE
        if state == "CHECKED_IN":
            return RoomStatus.OCCUPIED
        if state == "CONFIRMED":
            return RoomStatus.RESERVED
        return RoomStatus.AVAILABLE

    def _protect_future_bookings(self, uow: UnitOfWork, room: Room) -> None:
        """Story 3.8: a room change must never strand a guest who already booked it."""
        bookings = uow.reservations.future_bookings_for_room(room.id, self._clock.today())
        if not bookings:
            return
        if not room.in_service:
            raise ConflictError(
                "room.has_future_bookings",
                codes=", ".join(b.code for b in bookings[:5]),
                count=len(bookings),
            )
        too_many = [
            b
            for b in bookings
            if any(r.room_id == room.id and r.occupants > room.capacity for r in b.rooms)
        ]
        if too_many:
            raise ConflictError(
                "room.capacity_conflict",
                fields={"capacity": "room.capacity_conflict"},
                codes=", ".join(b.code for b in too_many[:5]),
            )

    @staticmethod
    def _load(uow: UnitOfWork, room_id: int) -> Room:
        room = uow.rooms.get(room_id)
        if room is None:
            raise NotFoundError(entity="room", id=room_id)
        return room

    @staticmethod
    def _check_room(uow: UnitOfWork, room: Room) -> None:
        if uow.categories.get(room.category_id) is None:
            raise ValidationError(
                "room.category_unknown", fields={"category_id": "room.category_unknown"}
            )
        if uow.rooms.number_taken(room.number, except_id=room.id):
            raise ConflictError("room.number_taken", fields={"number": "room.number_taken"})

"""Room categories, rooms and maintenance periods.

Categories (Standard, Deluxe, Suite...) differ in data, not behaviour, so they
are records chosen by the manager rather than Python subclasses: adding a
"Family room" category needs no code change.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from hotel.domain.errors import ValidationError
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod

MAX_CAPACITY = 10
MAX_NIGHTLY_RATE = Money.from_dinars(100_000)
MAX_MAINTENANCE_NIGHTS = 90
_ROOM_NUMBER = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,9}$")


class RoomStatus(StrEnum):
    """What a room is doing tonight (§4.5: reserved, occupied, available, unavailable)."""

    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class Housekeeping(StrEnum):
    """Is the room ready for the next guest? (story 4.9)

    Check-out makes a room DIRTY; housekeeping cleans it (CLEAN); a second
    person checks it (INSPECTED) and only then is it ready for a guest.
    """

    DIRTY = "DIRTY"
    CLEAN = "CLEAN"  # cleaned, waiting for the inspection
    INSPECTED = "INSPECTED"

    @property
    def is_ready(self) -> bool:
        return self is Housekeeping.INSPECTED


def _clean(raw: str) -> str:
    return " ".join(unicodedata.normalize("NFC", raw).split())


def validate_room_number(raw: str) -> str:
    number = unicodedata.normalize("NFKC", raw).strip().upper()
    if not _ROOM_NUMBER.fullmatch(number):
        raise ValidationError("room.number_invalid", fields={"number": "room.number_invalid"})
    return number


def validate_category_name(raw: str) -> str:
    name = _clean(raw)
    if not 1 <= len(name) <= 50:
        raise ValidationError("category.name_invalid", fields={"name": "category.name_invalid"})
    return name


def validate_capacity(capacity: int) -> int:
    if not 1 <= capacity <= MAX_CAPACITY:
        raise ValidationError(
            "room.capacity_invalid", fields={"capacity": "room.capacity_invalid"}, max=MAX_CAPACITY
        )
    return capacity


def validate_nightly_rate(rate: Money) -> Money:
    if rate.millimes <= 0 or rate > MAX_NIGHTLY_RATE:
        raise ValidationError("room.rate_invalid", fields={"nightly_rate": "room.rate_invalid"})
    return rate


def validate_text(raw: str, field: str, *, max_length: int, required: bool = False) -> str:
    value = unicodedata.normalize("NFC", raw).strip()
    if len(value) > max_length or (required and not value):
        code = f"{field}.invalid"
        raise ValidationError(code, fields={field: code}, max_length=max_length)
    return value


@dataclass(slots=True)
class RoomCategory:
    id: int | None
    name: str
    description: str = ""
    version: int = 1
    room_count: int = 0  # filled when listing


@dataclass(slots=True)
class Room:
    id: int | None
    number: str
    category_id: int
    capacity: int
    nightly_rate: Money
    in_service: bool = True
    notes: str = ""
    version: int = 1
    category_name: str | None = None  # filled when read from the database
    housekeeping: Housekeeping = Housekeeping.INSPECTED
    archived_at: datetime | None = None  # story 6.17

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def can_host(self, occupants: int) -> bool:
        return 1 <= occupants <= self.capacity  # business rule BR7


@dataclass(frozen=True, slots=True)
class MaintenancePeriod:
    id: int | None
    room_id: int
    period: StayPeriod  # [first closed night, reopening day)
    reason: str
    created_by: int | None = None
    created_at: datetime | None = None

    @property
    def first_night(self) -> date:
        return self.period.arrival

    @property
    def last_night(self) -> date:
        return self.period.departure - timedelta(days=1)

    @property
    def reopens_on(self) -> date:
        return self.period.departure


@dataclass(frozen=True, slots=True)
class RoomOverview:
    room: Room
    status: RoomStatus

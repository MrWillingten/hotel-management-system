"""What a room costs on a given night (story 5.6).

Priority, as agreed in the plan: a **rate period** of the room's category
(for example "Summer 2026: 220 DT") beats the **weekend surcharge**, which
beats the room's **base rate**. The result is copied onto each booked night
(BR20), so changing a period later never changes an existing reservation.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

from hotel.domain.errors import ValidationError
from hotel.domain.money import BASIS_POINTS_PER_UNIT, Money
from hotel.domain.period import StayPeriod
from hotel.domain.rooms import MAX_NIGHTLY_RATE, Room

MAX_PERIOD_NIGHTS = 366


@dataclass(frozen=True, slots=True)
class RatePeriod:
    id: int | None
    category_id: int
    name: str
    period: StayPeriod  # [first night, day after the last night)
    nightly_rate: Money
    category_name: str = ""  # filled when read
    created_at: datetime | None = None

    @property
    def last_night(self) -> date:
        return date.fromordinal(self.period.departure.toordinal() - 1)


def validate_rate_period(name: str, period: StayPeriod, rate: Money) -> str:
    name = " ".join(unicodedata.normalize("NFC", name).split())
    if not 1 <= len(name) <= 60:
        raise ValidationError(
            "rate_period.name_invalid", fields={"name": "rate_period.name_invalid"}
        )
    if period.nights > MAX_PERIOD_NIGHTS:
        raise ValidationError(
            "rate_period.too_long",
            fields={"last_night": "rate_period.too_long"},
            max=MAX_PERIOD_NIGHTS,
        )
    if rate.millimes <= 0 or rate > MAX_NIGHTLY_RATE:
        raise ValidationError("room.rate_invalid", fields={"nightly_rate": "room.rate_invalid"})
    return name


@dataclass(frozen=True, slots=True)
class Pricing:
    """Everything needed to price a night, read once per transaction."""

    periods: tuple[RatePeriod, ...] = ()
    weekend_nights: frozenset[int] = frozenset()  # date.weekday(): Monday 0 ... Sunday 6
    weekend_surcharge_bp: int = 0

    def rate_for(self, room: Room, night: date) -> Money:
        for period in self.periods:
            if period.category_id == room.category_id and period.period.contains(night):
                return period.nightly_rate
        if self.weekend_surcharge_bp and night.weekday() in self.weekend_nights:
            return room.nightly_rate.percent(BASIS_POINTS_PER_UNIT + self.weekend_surcharge_bp)
        return room.nightly_rate

"""Stay periods as half-open date ranges.

A stay from 10 July to 15 July is written [10 July, 15 July): the guest sleeps
the nights of the 10th, 11th, 12th, 13th and 14th and leaves on the 15th.
The departure day is *not* part of the stay, so another guest may arrive on
the 15th. With this convention two stays overlap exactly when

    a1 < d2 and a2 < d1

and the number of nights is simply departure - arrival.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from hotel.domain.errors import ValidationError


def _require_plain_date(value: object, name: str) -> None:
    # datetime is a subclass of date, but a stay is about calendar days only.
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime.date, got {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class StayPeriod:
    arrival: date
    departure: date

    def __post_init__(self) -> None:
        _require_plain_date(self.arrival, "arrival")
        _require_plain_date(self.departure, "departure")
        if self.departure <= self.arrival:  # business rule BR4
            raise ValidationError(
                "period.departure_not_after_arrival",
                fields={"departure": "period.departure_not_after_arrival"},
                arrival=self.arrival.isoformat(),
                departure=self.departure.isoformat(),
            )

    @property
    def nights(self) -> int:
        return (self.departure - self.arrival).days

    def overlaps(self, other: StayPeriod) -> bool:
        return self.arrival < other.departure and other.arrival < self.departure

    def contains(self, day: date) -> bool:
        """True if the guest sleeps at the hotel on the night starting on `day`."""
        return self.arrival <= day < self.departure

    def each_night(self) -> Iterator[date]:
        for offset in range(self.nights):
            yield self.arrival + timedelta(days=offset)

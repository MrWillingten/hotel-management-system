"""The night audit (story 5.4): closing a business day.

A hotel "closes" each day once it is over: guests who never came become
no-shows, guests who should have left are flagged, and the day's figures
are frozen in a snapshot that later changes cannot alter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from hotel.domain.money import Money
from hotel.domain.reports import rate_bp

MAX_CATCH_UP_DAYS = 31  # after a long shutdown, only the last month is closed automatically


@dataclass(frozen=True, slots=True)
class DailySnapshot:
    day: date
    nights_sold: int
    nights_sellable: int
    room_value: Money
    invoiced: Money
    cash: Money
    reservations_made: int
    cancellations: int
    no_shows: int
    overdue_departures: int
    created_at: datetime | None = None
    created_by_name: str = ""

    @property
    def occupancy_bp(self) -> int:
        return rate_bp(self.nights_sold, self.nights_sellable)


@dataclass(frozen=True, slots=True)
class AuditOutcome:
    """What one run did. `already_closed` means the day had been closed before."""

    day: date
    snapshot: DailySnapshot
    no_shows: list[str] = field(default_factory=list)  # reservation codes marked now
    overdue: list[str] = field(default_factory=list)  # still checked in after departure
    already_closed: bool = False


def days_to_close(last_closed: date | None, today: date) -> list[date]:
    """Every finished day not closed yet: at most a month back, never today."""
    yesterday = date.fromordinal(today.toordinal() - 1)
    if last_closed is None:
        return [yesterday]
    first = max(last_closed.toordinal() + 1, today.toordinal() - MAX_CATCH_UP_DAYS)
    return [date.fromordinal(n) for n in range(first, today.toordinal())]

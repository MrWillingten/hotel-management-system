"""Management statistics (brief §4.8, story 5.1).

The figures are read-only summaries of data stored elsewhere, so this module
only holds the shapes and the arithmetic (rates, averages, monthly totals);
the SQL that gathers them lives in persistence/repositories/reports.py.

Definitions, so every number can be explained:
* a **night sold** is one room reserved for one night (any active or past
  stay; cancelled and no-show nights were released, so they do not count);
* **occupancy** = nights sold / nights sellable (decision H): rooms in service
  minus rooms under maintenance that night;
* **revenue** counts when an invoice is issued (accrual); the money actually
  received in the period is shown separately ("cash received");
* **ADR** (average daily rate) = room value of the nights sold / nights sold;
  **RevPAR** (revenue per available room) = room value / nights sellable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from hotel.domain.errors import ValidationError
from hotel.domain.money import BASIS_POINTS_PER_UNIT, Money

MAX_RANGE_DAYS = 731  # two years, inclusive (threat W9: no unbounded queries)


def validate_range(first: date, last: date) -> tuple[date, date]:
    """A report covers the nights first..last, both included."""
    if last < first:
        raise ValidationError("report.range_reversed", fields={"last": "report.range_reversed"})
    if (last - first).days + 1 > MAX_RANGE_DAYS:
        raise ValidationError(
            "report.range_too_long", fields={"last": "report.range_too_long"}, max=MAX_RANGE_DAYS
        )
    return first, last


def rate_bp(part: int, whole: int) -> int:
    """part / whole in basis points (7550 = 75.50 %), rounded down; 0 when whole is 0."""
    return part * BASIS_POINTS_PER_UNIT // whole if whole else 0


def average(total: Money, count: int) -> Money:
    """Total / count rounded half-up to the millime (zero when there is nothing to divide)."""
    if not count:
        return Money.zero()
    return Money((2 * total.millimes + count) // (2 * count))  # half-up for positive totals


@dataclass(frozen=True, slots=True)
class DayFigures:
    night: date
    sold: int
    sellable: int
    room_value: Money  # the locked prices of the nights sold

    @property
    def occupancy_bp(self) -> int:
        return rate_bp(self.sold, self.sellable)


@dataclass(frozen=True, slots=True)
class MonthFigures:
    month: date  # first day of the month
    sold: int
    sellable: int
    room_value: Money

    @property
    def occupancy_bp(self) -> int:
        return rate_bp(self.sold, self.sellable)


@dataclass(frozen=True, slots=True)
class CategoryFigures:
    name: str
    nights: int
    room_value: Money


@dataclass(frozen=True, slots=True)
class CategoryAvailability:
    name: str
    rooms: int  # in service
    maintenance: int
    sold: int

    @property
    def free(self) -> int:
        return self.rooms - self.maintenance - self.sold


@dataclass(frozen=True, slots=True)
class Count:
    """How many, and the fees they produced (cancellations, no-shows)."""

    count: int = 0
    fees: Money = field(default_factory=Money.zero)


@dataclass(frozen=True, slots=True)
class Report:
    first: date
    last: date
    days: list[DayFigures]
    reservations_made: int
    invoices: int
    invoiced: dict[str, Money]  # invoice line kind -> amount (NIGHTS, EXTRA, FEE, DISCOUNT, TAX...)
    cash: dict[str, Money]  # payment method -> net amount received (refunds subtracted)
    cancellations: Count
    no_shows: Count
    categories: list[CategoryFigures]
    availability_day: date
    availability: list[CategoryAvailability]
    unpaid: list[tuple[int, str, str, Money]]  # after check-out
    in_house_due: Money

    # ------------------------------------------------------------ occupancy
    @property
    def nights_sold(self) -> int:
        return sum(d.sold for d in self.days)

    @property
    def nights_sellable(self) -> int:
        return sum(d.sellable for d in self.days)

    @property
    def occupancy_bp(self) -> int:
        return rate_bp(self.nights_sold, self.nights_sellable)

    @property
    def room_value(self) -> Money:
        total = Money.zero()
        for day in self.days:
            total += day.room_value
        return total

    @property
    def adr(self) -> Money:
        return average(self.room_value, self.nights_sold)

    @property
    def revpar(self) -> Money:
        return average(self.room_value, self.nights_sellable)

    def months(self) -> list[MonthFigures]:
        """The days added up per calendar month, for long ranges."""
        totals: dict[date, list] = {}
        for day in self.days:
            key = day.night.replace(day=1)
            sold, sellable, value = totals.get(key, (0, 0, Money.zero()))
            totals[key] = (sold + day.sold, sellable + day.sellable, value + day.room_value)
        return [MonthFigures(k, *v) for k, v in sorted(totals.items())]

    # ------------------------------------------------------------ revenue
    def invoiced_as(self, *kinds: str) -> Money:
        total = Money.zero()
        for kind in kinds:
            total += self.invoiced.get(kind, Money.zero())
        return total

    @property
    def accommodation(self) -> Money:
        """Nights invoiced, after discounts."""
        return self.invoiced_as("NIGHTS", "DISCOUNT", "DISCOUNT_CAP")

    @property
    def services(self) -> Money:
        return self.invoiced_as("EXTRA")

    @property
    def taxes(self) -> Money:
        return self.invoiced_as("TAX")

    @property
    def fees(self) -> Money:
        return self.invoiced_as("FEE")

    @property
    def revenue(self) -> Money:
        """Everything invoiced in the period, taxes included."""
        total = Money.zero()
        for amount in self.invoiced.values():
            total += amount
        return total

    @property
    def cash_received(self) -> Money:
        total = Money.zero()
        for amount in self.cash.values():
            total += amount
        return total

    @property
    def outstanding(self) -> Money:
        total = self.in_house_due
        for *_, due in self.unpaid:
            total += due
        return total


def nights_between(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]

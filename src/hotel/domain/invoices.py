"""Invoices (BR22): a frozen copy of the bill at the moment it is issued.

An invoice copies every line and total instead of pointing at the live data,
so a later price, tax or name change can never alter it. Payments are not
copied: they are append-only and dated, so "paid when issued" is simply the
payments made up to `issued_at`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from hotel.domain.billing import Bill, BillLine, Payment
from hotel.domain.money import Money


def invoice_number(year: int, sequence: int) -> str:
    """Gap-free yearly numbers, as invoices legally require: F-2026-00001."""
    return f"F-{year}-{sequence:05d}"


@dataclass(frozen=True, slots=True)
class Invoice:
    id: int | None
    number: str
    reservation_id: int
    reservation_code: str
    guest_name: str
    arrival: date
    departure: date
    issued_at: datetime
    issued_by_name: str = ""
    lines: list[BillLine] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)  # made up to issued_at
    listed_total: Money | None = None  # the stored total, filled in lists (no lines loaded)

    @property
    def bill(self) -> Bill:
        """The same totals as the bill it was issued from (tested)."""
        return Bill(self.lines, self.payments)

    @property
    def total(self) -> Money:
        return self.bill.total

    @property
    def balance(self) -> Money:
        return self.bill.balance

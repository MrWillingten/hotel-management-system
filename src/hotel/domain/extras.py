"""Extra services (breakfast, airport transfer...) and what they cost a guest.

They are called "extras" in the code so they are never confused with the
application's service layer (hotel.services).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

from hotel.domain.errors import BusinessRuleViolation, ValidationError
from hotel.domain.money import Money
from hotel.domain.reservations import Reservation, ReservationStatus

MAX_QUANTITY = 99
MAX_UNIT_PRICE = Money.from_dinars(10_000)
MAX_NAME = 60
MAX_REASON = 200


def validate_extra_name(raw: str) -> str:
    name = " ".join(unicodedata.normalize("NFC", raw).split())
    if not 1 <= len(name) <= MAX_NAME:
        raise ValidationError("extra.name_invalid", fields={"name": "extra.name_invalid"})
    return name


def validate_unit_price(price: Money) -> Money:
    if price.millimes <= 0 or price > MAX_UNIT_PRICE:
        raise ValidationError("extra.price_invalid", fields={"unit_price": "extra.price_invalid"})
    return price


@dataclass(slots=True)
class Extra:
    """An item of the catalogue. Deleted if never charged, otherwise archived (story 6.17)."""

    id: int | None
    name: str
    unit_price: Money
    is_active: bool = True
    version: int = 1
    archived_at: datetime | None = None

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


@dataclass(slots=True)
class ServiceCharge:
    """One extra charged to a stay.

    The name and price are copied from the catalogue when the charge is made
    (BR20): changing the catalogue later never changes a guest's bill.
    """

    id: int | None
    reservation_id: int
    extra_id: int
    description: str
    quantity: int
    unit_price: Money
    charge_date: date
    created_by: int | None = None
    created_at: datetime | None = None
    voided_at: datetime | None = None
    voided_by: int | None = None
    void_reason: str | None = None

    @property
    def amount(self) -> Money:
        return self.unit_price.times(self.quantity)

    @property
    def is_void(self) -> bool:
        return self.voided_at is not None


def validate_charge(
    reservation: Reservation, charge_date: date, quantity: int, today: date
) -> None:
    """Business rule BR19: only while the guest is in the house, dated within the stay.

    The departure day is allowed (a breakfast or the minibar on the last
    morning); a future date is not, because the service has not happened yet.
    """
    if reservation.status is not ReservationStatus.CHECKED_IN:
        raise BusinessRuleViolation("charge.not_in_house")
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ValidationError(
            "charge.quantity_invalid",
            fields={"quantity": "charge.quantity_invalid"},
            max=MAX_QUANTITY,
        )
    period = reservation.period
    if not period.arrival <= charge_date <= period.departure or charge_date > today:
        raise ValidationError(
            "charge.date_outside_stay",
            fields={"charge_date": "charge.date_outside_stay"},
            arrival=period.arrival.isoformat(),
            last=min(period.departure, today).isoformat(),
        )


def validate_void_reason(raw: str) -> str:
    reason = unicodedata.normalize("NFC", raw).strip()
    if not 1 <= len(reason) <= MAX_REASON:
        raise ValidationError(
            "reason.invalid", fields={"reason": "reason.invalid"}, max_length=MAX_REASON
        )
    return reason

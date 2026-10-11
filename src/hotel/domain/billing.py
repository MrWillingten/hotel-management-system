"""The guest's bill: nights, extras, discounts, taxes, payments and balance.

`build_bill()` is a pure function: given what is stored for a reservation it
returns every line and total, so the preview, the balance shown at the desk
and the invoice issued at check-out are always computed the same way.

Rounding: every amount is exact in millimes; percentages are rounded half-up
once per line (Money.percent), and totals are plain sums of those lines.
"""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from hotel.domain.errors import BusinessRuleViolation, ValidationError
from hotel.domain.extras import ServiceCharge
from hotel.domain.money import BASIS_POINTS_PER_UNIT, Money
from hotel.domain.reservations import Reservation, ReservationStatus
from hotel.domain.taxes import TaxableStay, TaxRule

MAX_PAYMENT = Money.from_dinars(1_000_000)
MAX_REASON = 200
MAX_REFERENCE = 60


# ---------------------------------------------------------------- discounts (Strategy)
@dataclass(kw_only=True, slots=True)
class Discount(ABC):
    """Decision Q3: manager only, reason required, accommodation only, capped."""

    id: int | None = None
    reservation_id: int
    reason: str
    approved_by: int | None = None
    approved_by_name: str = ""  # filled when read, for display
    created_at: datetime | None = None
    removed_at: datetime | None = None

    @abstractmethod
    def amount(self, accommodation: Money) -> Money:
        """How much this discount takes off the given accommodation total."""

    @abstractmethod
    def validate(self) -> None: ...

    @property
    def is_active(self) -> bool:
        return self.removed_at is None

    def _validate_reason(self) -> None:
        reason = unicodedata.normalize("NFC", self.reason).strip()
        if not 1 <= len(reason) <= MAX_REASON:
            raise ValidationError(
                "reason.invalid", fields={"reason": "reason.invalid"}, max_length=MAX_REASON
            )
        self.reason = reason


@dataclass(kw_only=True, slots=True)
class PercentDiscount(Discount):
    rate_bp: int

    def amount(self, accommodation: Money) -> Money:
        return accommodation.percent(self.rate_bp)

    def validate(self) -> None:
        self._validate_reason()
        if not 1 <= self.rate_bp <= BASIS_POINTS_PER_UNIT:
            raise ValidationError(
                "discount.rate_invalid", fields={"value": "discount.rate_invalid"}
            )


@dataclass(kw_only=True, slots=True)
class FixedDiscount(Discount):
    value: Money

    def amount(self, accommodation: Money) -> Money:
        # Never more than what it is taken from, so a shortened stay stays >= 0.
        return min(self.value, accommodation)

    def validate(self) -> None:
        self._validate_reason()
        if self.value.millimes <= 0 or self.value > MAX_PAYMENT:
            raise ValidationError(
                "discount.amount_invalid", fields={"value": "discount.amount_invalid"}
            )


def discount_total(discounts: list[Discount], accommodation: Money, cap_bp: int) -> Money:
    """The sum of the active discounts, never above the cap (default 30 %)."""
    raw = Money.zero()
    for discount in discounts:
        if discount.is_active:
            raw += discount.amount(accommodation)
    return min(raw, accommodation.percent(cap_bp))


def check_discount_cap(
    discounts: list[Discount], new: Discount, accommodation: Money, cap_bp: int
) -> None:
    """Refuse a new discount that would take the total over the cap."""
    total = new.amount(accommodation)
    for discount in discounts:
        if discount.is_active:
            total += discount.amount(accommodation)
    cap = accommodation.percent(cap_bp)
    if total > cap:
        raise BusinessRuleViolation("discount.over_cap", cap=str(cap), requested=str(total))


# ---------------------------------------------------------------- payments
class PaymentKind(StrEnum):
    DEPOSIT = "DEPOSIT"  # before arrival (BR10)
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"


class PaymentMethod(StrEnum):
    CASH = "CASH"
    CARD = "CARD"
    TRANSFER = "TRANSFER"


@dataclass(slots=True)
class Payment:
    """Money received or given back. Append-only: a mistake is corrected by a refund."""

    id: int | None
    reservation_id: int
    kind: PaymentKind
    method: PaymentMethod
    amount: Money  # always positive (BR21); the kind says which way it goes
    paid_at: datetime
    reference: str = ""
    recorded_by: int | None = None
    recorded_by_name: str = ""  # filled when read, for display

    @property
    def signed_amount(self) -> Money:
        return -self.amount if self.kind is PaymentKind.REFUND else self.amount


def validate_amount(amount: Money) -> Money:
    if amount.millimes <= 0 or amount > MAX_PAYMENT:
        raise ValidationError("payment.amount_invalid", fields={"amount": "payment.amount_invalid"})
    return amount


def validate_reference(raw: str) -> str:
    reference = unicodedata.normalize("NFC", raw).strip()
    if len(reference) > MAX_REFERENCE:
        raise ValidationError(
            "reference.invalid", fields={"reference": "reference.invalid"}, max_length=MAX_REFERENCE
        )
    return reference


def payment_kind_for(status: ReservationStatus) -> PaymentKind:
    """Money received before arrival is a deposit (BR10); afterwards a payment."""
    return PaymentKind.DEPOSIT if status is ReservationStatus.CONFIRMED else PaymentKind.PAYMENT


# ---------------------------------------------------------------- the bill
class LineKind(StrEnum):
    NIGHTS = "NIGHTS"
    EXTRA = "EXTRA"
    FEE = "FEE"
    DISCOUNT = "DISCOUNT"
    DISCOUNT_CAP = "DISCOUNT_CAP"  # gives back what exceeds the cap
    TAX = "TAX"


@dataclass(frozen=True, slots=True)
class BillLine:
    """One line. `label` is data (room number, extra name, tax name, reason);
    the interface turns `kind` into words in the reader's language."""

    kind: LineKind
    label: str
    quantity: int
    unit: Money
    amount: Money  # discounts are negative
    first: date | None = None  # nights: first night; extras: charge date
    last: date | None = None  # nights: last night
    rate_bp: int | None = None  # percentage taxes: the rate applied to `unit`


@dataclass(frozen=True, slots=True)
class Bill:
    lines: list[BillLine] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)

    def _sum(self, *kinds: LineKind) -> Money:
        total = Money.zero()
        for line in self.lines:
            if line.kind in kinds:
                total += line.amount
        return total

    @property
    def accommodation(self) -> Money:
        return self._sum(LineKind.NIGHTS)

    @property
    def extras(self) -> Money:
        return self._sum(LineKind.EXTRA)

    @property
    def fees(self) -> Money:
        return self._sum(LineKind.FEE)

    @property
    def discount(self) -> Money:
        """Positive: what was taken off."""
        return -self._sum(LineKind.DISCOUNT, LineKind.DISCOUNT_CAP)

    @property
    def subtotal(self) -> Money:
        """Before discounts and taxes."""
        return self._sum(LineKind.NIGHTS, LineKind.EXTRA, LineKind.FEE)

    @property
    def tax(self) -> Money:
        return self._sum(LineKind.TAX)

    @property
    def total(self) -> Money:
        return self._sum(*LineKind)

    @property
    def paid(self) -> Money:
        paid = Money.zero()
        for payment in self.payments:
            paid += payment.signed_amount
        return paid

    @property
    def balance(self) -> Money:
        """BR21: positive = the guest owes; negative = the hotel owes a refund."""
        return self.total - self.paid


def _night_lines(reservation: Reservation) -> list[BillLine]:
    """One line per room and run of consecutive nights at the same price."""
    lines = []
    for room in reservation.rooms:
        run: list = []
        for night in [*reservation.nights_of(room.room_id), None]:  # None closes the last run
            if run and (
                night is None
                or night.rate != run[-1].rate
                or (night.night - run[-1].night).days != 1
            ):
                lines.append(
                    BillLine(
                        LineKind.NIGHTS,
                        room.number,
                        len(run),
                        run[0].rate,
                        run[0].rate.times(len(run)),
                        run[0].night,
                        run[-1].night,
                    )
                )
                run = []
            if night is not None:
                run.append(night)
    return lines


def adult_nights(reservation: Reservation) -> int:
    """For per-person taxes: adults of each room x the nights charged for it."""
    return sum(room.adults * len(reservation.nights_of(room.room_id)) for room in reservation.rooms)


def build_bill(
    reservation: Reservation,
    *,
    charges: list[ServiceCharge],
    discounts: list[Discount],
    taxes: list[TaxRule],
    payments: list[Payment],
    discount_cap_bp: int,
) -> Bill:
    if reservation.status in (ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW):
        # Only the fee is owed; it is not taxed (decision Q2).
        fee = reservation.cancellation_fee or Money.zero()
        lines = [] if fee.is_zero() else [BillLine(LineKind.FEE, reservation.status, 1, fee, fee)]
        return Bill(lines, payments)

    lines = _night_lines(reservation)
    lines += [
        BillLine(LineKind.EXTRA, c.description, c.quantity, c.unit_price, c.amount, c.charge_date)
        for c in charges
        if not c.is_void
    ]
    accommodation = reservation.accommodation_total
    active = [d for d in discounts if d.is_active]
    for discount in active:
        amount = discount.amount(accommodation)
        lines.append(BillLine(LineKind.DISCOUNT, discount.reason, 1, -amount, -amount))
    granted = discount_total(active, accommodation, discount_cap_bp)
    raw = Money.zero()
    for discount in active:
        raw += discount.amount(accommodation)
    if raw > granted:
        # A shortened stay can push old discounts over the cap: give back the excess.
        excess = raw - granted
        lines.append(BillLine(LineKind.DISCOUNT_CAP, "", 1, excess, excess))

    services = Money.zero()
    for charge in charges:
        if not charge.is_void:
            services += charge.amount
    taxable = TaxableStay(accommodation - granted, services, adult_nights(reservation))
    for rule in taxes:
        if rule.is_active:
            amount = rule.amount(taxable)
            if not amount.is_zero():
                quantity, unit = rule.basis(taxable)
                lines.append(
                    BillLine(
                        LineKind.TAX,
                        rule.name,
                        quantity,
                        unit,
                        amount,
                        rate_bp=getattr(rule, "rate_bp", None),
                    )
                )
    return Bill(lines, payments)


def check_payment(bill: Bill, kind: PaymentKind, amount: Money) -> None:
    """Never take more than is owed, never give back more than was overpaid.

    This catches typing mistakes (1500 instead of 150) before they become a
    refund to chase; a real overpayment is recorded as the exact balance.
    """
    validate_amount(amount)
    if kind is PaymentKind.REFUND:
        credit = -bill.balance
        if amount > credit:
            raise BusinessRuleViolation(
                "payment.refund_too_large", credit=str(max(credit, Money.zero()))
            )
    elif amount > bill.balance:
        raise BusinessRuleViolation(
            "payment.more_than_due", due=str(max(bill.balance, Money.zero()))
        )

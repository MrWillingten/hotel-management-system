"""The bill, computed by the pure build_bill() function (stories 4.4-4.6)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from hotel.domain.billing import (
    Bill,
    FixedDiscount,
    LineKind,
    Payment,
    PaymentKind,
    PaymentMethod,
    PercentDiscount,
    build_bill,
    check_discount_cap,
    check_payment,
    discount_total,
    payment_kind_for,
)
from hotel.domain.errors import BusinessRuleViolation, ValidationError
from hotel.domain.extras import ServiceCharge
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import BookedRoom, Reservation, ReservationStatus, RoomNight
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxBase

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
DT = Money.from_dinars


def _stay(nights=3, rate=150, adults=2, status=ReservationStatus.CHECKED_IN, rates=None):
    period = StayPeriod(date(2026, 7, 10), date(2026, 7, 10) + timedelta(days=nights))
    rates = rates or [rate] * nights
    return Reservation(
        1,
        "R-2026-00001",
        1,
        period,
        status=status,
        rooms=[BookedRoom(7, adults, 0, "204", "Deluxe")],
        nights=[RoomNight(7, n, DT(r)) for n, r in zip(period.each_night(), rates, strict=True)],
    )


def _charge(amount, quantity=1, void=False):
    return ServiceCharge(
        None,
        1,
        1,
        "Breakfast",
        quantity,
        DT(amount),
        date(2026, 7, 11),
        voided_at=NOW if void else None,
        void_reason="x" if void else None,
    )


def _pay(amount, kind=PaymentKind.DEPOSIT):
    return Payment(None, 1, kind, PaymentMethod.CASH, DT(amount), NOW)


def _bill(reservation, charges=(), discounts=(), taxes=(), payments=(), cap=3000):
    return build_bill(
        reservation,
        charges=list(charges),
        discounts=list(discounts),
        taxes=list(taxes),
        payments=list(payments),
        discount_cap_bp=cap,
    )


# ---------------------------------------------------------------- golden tests (brief §4.7)
def test_scenario_4_7_three_nights_services_and_a_deposit():
    """3 nights x 150 DT, 80 DT of services, 100 DT deposit: total 530, balance 430."""
    bill = _bill(_stay(), charges=[_charge(80)], payments=[_pay(100)])
    assert bill.accommodation == DT(450)
    assert bill.extras == DT(80)
    assert bill.total == DT(530)
    assert bill.paid == DT(100)
    assert bill.balance == DT(430)


def test_scenario_4_7_with_tunisian_style_taxes():
    """The same stay with VAT 7 % on rooms, 19 % on services and 3 DT/adult/night."""
    taxes = [
        PercentTax(name="VAT", rate_bp=700),
        PercentTax(name="VAT services", rate_bp=1900, applies_to=TaxBase.SERVICES),
        PerAdultNightTax(name="Tourist tax", amount_per=DT(3)),
    ]
    bill = _bill(_stay(adults=2), charges=[_charge(80)], taxes=taxes, payments=[_pay(100)])
    tax_lines = [
        (line.label, line.quantity, line.unit, line.amount)
        for line in bill.lines
        if line.kind is LineKind.TAX
    ]
    assert tax_lines == [
        ("VAT", 1, DT(450), Money(31_500)),
        ("VAT services", 1, DT(80), Money(15_200)),
        ("Tourist tax", 6, DT(3), DT(18)),  # 2 adults x 3 nights
    ]
    assert bill.tax == Money(64_700)
    assert bill.total == Money(594_700)
    assert bill.balance == Money(494_700)


# ---------------------------------------------------------------- lines
def test_nights_are_grouped_by_price():
    bill = _bill(_stay(nights=4, rates=[150, 150, 200, 150]))
    nights = [(line.quantity, line.unit, line.first, line.last) for line in bill.lines]
    assert nights == [
        (2, DT(150), date(2026, 7, 10), date(2026, 7, 11)),
        (1, DT(200), date(2026, 7, 12), date(2026, 7, 12)),
        (1, DT(150), date(2026, 7, 13), date(2026, 7, 13)),
    ]
    assert bill.accommodation == DT(650)


def test_voided_charges_are_not_billed():
    bill = _bill(_stay(), charges=[_charge(15, 2), _charge(40, void=True)])
    assert bill.extras == DT(30)
    assert [line.label for line in bill.lines if line.kind is LineKind.EXTRA] == ["Breakfast"]


def test_cancelled_and_no_show_bills_hold_only_the_untaxed_fee():
    vat = PercentTax(name="VAT", rate_bp=700)
    for status in (ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW):
        reservation = _stay(status=status)
        reservation.nights = []  # released
        reservation.cancellation_fee = DT(90)
        bill = _bill(reservation, taxes=[vat], payments=[_pay(100)])
        assert [(line.kind, line.label) for line in bill.lines] == [(LineKind.FEE, status)]
        assert bill.total == DT(90)
        assert bill.balance == DT(-10)  # the hotel owes a 10 DT refund


def test_free_cancellation_leaves_an_empty_bill():
    reservation = _stay(status=ReservationStatus.CANCELLED)
    reservation.cancellation_fee = Money.zero()
    assert _bill(reservation).lines == []


# ---------------------------------------------------------------- discounts (Strategy)
def _percent(bp, reason="Loyal guest"):
    return PercentDiscount(reservation_id=1, reason=reason, rate_bp=bp)


def _fixed(dinars, reason="Noise complaint"):
    return FixedDiscount(reservation_id=1, reason=reason, value=DT(dinars))


def test_discounts_apply_to_accommodation_only_and_before_tax():
    vat = PercentTax(name="VAT", rate_bp=1000)
    bill = _bill(_stay(), charges=[_charge(80)], discounts=[_percent(1000)], taxes=[vat])
    assert bill.discount == DT(45)  # 10 % of 450, not of the services
    assert bill.tax == Money(40_500)  # 10 % of (450 - 45)
    assert bill.total == DT(450 + 80 - 45) + Money(40_500)


def test_fixed_discount_never_exceeds_what_it_is_taken_from():
    assert _fixed(500).amount(DT(450)) == DT(450)
    assert _fixed(50).amount(DT(450)) == DT(50)


def test_total_discount_is_capped():
    discounts = [_percent(2000), _fixed(100)]  # 90 + 100 = 190 > 30 % of 450 = 135
    assert discount_total(discounts, DT(450), 3000) == DT(135)
    bill = _bill(_stay(), discounts=discounts)
    assert bill.discount == DT(135)
    assert [line.kind for line in bill.lines][-1] is LineKind.DISCOUNT_CAP


def test_removed_discounts_do_not_count():
    removed = _percent(2000)
    removed.removed_at = NOW
    assert _bill(_stay(), discounts=[removed]).discount.is_zero()


def test_new_discounts_over_the_cap_are_refused():
    check_discount_cap([_percent(2000)], _percent(1000), DT(450), 3000)  # exactly 30 %
    with pytest.raises(BusinessRuleViolation, match="over_cap"):
        check_discount_cap([_percent(2000)], _fixed(46), DT(450), 3000)


def test_discount_validation():
    for discount in (_percent(0), _percent(10_001), _fixed(0), _percent(100, reason="  ")):
        with pytest.raises(ValidationError):
            discount.validate()


# ---------------------------------------------------------------- payments
def test_deposit_before_arrival_payment_afterwards():
    assert payment_kind_for(ReservationStatus.CONFIRMED) is PaymentKind.DEPOSIT
    for status in (
        ReservationStatus.CHECKED_IN,
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.NO_SHOW,
    ):
        assert payment_kind_for(status) is PaymentKind.PAYMENT


def test_refunds_count_against_payments():
    bill = Bill(payments=[_pay(100), _pay(30, PaymentKind.REFUND)])
    assert bill.paid == DT(70)
    assert bill.balance == DT(-70)


def test_never_take_more_than_is_owed_or_refund_more_than_was_overpaid():
    bill = _bill(_stay(), payments=[_pay(400)])  # 450 due, 50 left
    check_payment(bill, PaymentKind.PAYMENT, DT(50))
    with pytest.raises(BusinessRuleViolation, match="more_than_due"):
        check_payment(bill, PaymentKind.PAYMENT, Money(50_001))
    with pytest.raises(BusinessRuleViolation, match="refund_too_large"):
        check_payment(bill, PaymentKind.REFUND, Money(1))
    with pytest.raises(ValidationError):
        check_payment(bill, PaymentKind.PAYMENT, Money(0))
    overpaid = _bill(_stay(), payments=[_pay(500)])
    check_payment(overpaid, PaymentKind.REFUND, DT(50))

"""Bill, discounts, payments and refunds against a real database (stories 4.4-4.6)."""

import sqlite3
from datetime import timedelta

import pytest

from hotel.domain.billing import FixedDiscount, PaymentKind, PaymentMethod, PercentDiscount
from hotel.domain.errors import (
    BusinessRuleViolation,
    NotFoundError,
    PermissionDeniedError,
)
from hotel.domain.money import Money
from hotel.domain.settings import HotelSettings
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxBase
from tests.integration.test_booking import book, stay

DT = Money.from_dinars
CASH = PaymentMethod.CASH


def _deluxe_150(services, hotel):
    """Room 204 at 150 DT a night, as in the brief's scenario §4.7."""
    room = hotel.rooms["204"]
    services.rooms.update_room(
        hotel.boss,
        room.id,
        version=room.version,
        number="204",
        category_id=room.category_id,
        capacity=2,
        nightly_rate=DT(150),
        in_service=True,
    )


def test_scenario_4_7_end_to_end(services, hotel, clock):
    """3 nights x 150 DT, 80 DT services, 100 DT deposit: 530 DT, 430 DT still due."""
    _deluxe_150(services, hotel)
    r = book(services, hotel, stay(8, 11), "204", adults=2)
    deposit = services.billing.record_payment(hotel.rita, r.id, amount=DT(100), method=CASH)
    assert deposit.kind is PaymentKind.DEPOSIT
    r = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    breakfast = services.extras.create(hotel.boss, name="Breakfast", unit_price=DT(20))
    services.extras.charge(hotel.rita, r.id, extra_id=breakfast.id, quantity=4)
    bill = services.billing.bill(hotel.rita, r.id)
    assert (bill.accommodation, bill.extras, bill.total) == (DT(450), DT(80), DT(530))
    assert (bill.paid, bill.balance) == (DT(100), DT(430))
    payment = services.billing.record_payment(hotel.rita, r.id, amount=DT(430), method=CASH)
    assert payment.kind is PaymentKind.PAYMENT
    assert services.billing.bill(hotel.rita, r.id).balance.is_zero()


def test_active_tax_rules_are_on_the_bill(services, hotel):
    _deluxe_150(services, hotel)
    settings = services.hotel_settings
    settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    settings.create_tax_rule(
        hotel.boss, PercentTax(name="VAT", rate_bp=1900, applies_to=TaxBase.SERVICES)
    )
    tourist = settings.create_tax_rule(
        hotel.boss, PerAdultNightTax(name="Tourist tax", amount_per=DT(3))
    )
    settings.update_tax_rule(
        hotel.boss,
        tourist.id,
        PerAdultNightTax(name="Tourist tax", amount_per=DT(3), is_active=False, version=1),
    )
    r = book(services, hotel, stay(8, 11), "204", adults=2)
    bill = services.billing.bill(hotel.rita, r.id)
    assert bill.tax == Money(31_500)  # no services yet, tourist tax inactive
    assert bill.total == Money(481_500)


def test_discounts_are_manager_only_capped_and_removable(services, hotel):
    r = book(services, hotel, stay(8, 11), "204")  # 540 DT
    ten = PercentDiscount(reservation_id=r.id, reason="Returning guest", rate_bp=1000)
    with pytest.raises(PermissionDeniedError):
        services.billing.grant_discount(hotel.rita, ten)
    services.billing.grant_discount(hotel.boss, ten)
    too_much = FixedDiscount(reservation_id=r.id, reason="Complaint", value=DT(109))
    with pytest.raises(BusinessRuleViolation, match="over_cap"):  # 54 + 109 > 162
        services.billing.grant_discount(hotel.boss, too_much)
    services.billing.grant_discount(
        hotel.boss, FixedDiscount(reservation_id=r.id, reason="Complaint", value=DT(108))
    )
    bill = services.billing.bill(hotel.rita, r.id)
    assert bill.discount == DT(162)
    assert bill.total == DT(378)
    [first, _] = services.billing.discounts(hotel.rita, r.id)
    assert first.approved_by_name == "Mona Ben Salah"
    services.billing.remove_discount(hotel.boss, first.id)
    assert services.billing.bill(hotel.rita, r.id).discount == DT(108)
    with pytest.raises(NotFoundError):
        services.billing.remove_discount(hotel.boss, first.id)
    with services.uow_factory() as uow:
        actions = [e.action for e in uow.audit.iterate()]
    assert actions.count("discount.granted") == 2
    assert "discount.removed" in actions


def test_the_cap_follows_the_settings(services, hotel):
    services.hotel_settings.update(hotel.boss, HotelSettings(discount_cap_bp=500))
    r = book(services, hotel, stay(8, 11), "204")
    with pytest.raises(BusinessRuleViolation, match="over_cap"):
        services.billing.grant_discount(
            hotel.boss, PercentDiscount(reservation_id=r.id, reason="x", rate_bp=600)
        )


def test_no_discount_once_the_bill_is_closed(services, hotel, clock):
    r = book(services, hotel, stay(9, 11), "204")
    services.reservations.cancel(hotel.rita, r.id, version=r.version)
    with pytest.raises(BusinessRuleViolation, match="bill_closed"):
        services.billing.grant_discount(
            hotel.boss, PercentDiscount(reservation_id=r.id, reason="x", rate_bp=100)
        )


def test_cancellation_fee_is_taken_from_the_deposit_and_the_rest_refunded(services, hotel):
    """Decision Q2: fee first from the deposit, any remainder refunded."""
    r = book(services, hotel, stay(9, 11), "204")  # 360 DT, arrival in 25 hours
    services.billing.record_payment(hotel.rita, r.id, amount=DT(100), method=CASH)
    services.reservations.cancel(hotel.rita, r.id, version=r.version)  # fee 72 DT
    bill = services.billing.bill(hotel.rita, r.id)
    assert (bill.total, bill.paid, bill.balance) == (DT(72), DT(100), DT(-28))
    with pytest.raises(PermissionDeniedError):
        services.billing.refund(hotel.rita, r.id, amount=DT(28), method=CASH)
    with pytest.raises(BusinessRuleViolation, match="refund_too_large"):
        services.billing.refund(hotel.boss, r.id, amount=DT(29), method=CASH)
    refund = services.billing.refund(hotel.boss, r.id, amount=DT(28), method=CASH, reference=" ")
    assert (refund.kind, refund.reference) == (PaymentKind.REFUND, "")
    assert services.billing.bill(hotel.rita, r.id).balance.is_zero()


def test_payments_never_exceed_the_balance(services, hotel):
    r = book(services, hotel, stay(9, 10), "101")  # 120 DT
    with pytest.raises(BusinessRuleViolation, match="more_than_due"):
        services.billing.record_payment(hotel.rita, r.id, amount=DT(121), method=CASH)


def test_payments_are_append_only_in_the_database(services, hotel):
    r = book(services, hotel, stay(9, 10), "101")
    services.billing.record_payment(hotel.rita, r.id, amount=DT(50), method=CASH)
    with services.uow_factory() as uow:
        conn = uow.payments._conn
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE payment SET amount_mill = 1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM payment")


def test_no_show_bill(services, hotel, clock):
    r = book(services, hotel, stay(8, 10), "204")  # 360 DT
    clock.advance(timedelta(hours=2))
    services.reservations.record_no_show(hotel.rita, r.id, version=r.version)
    bill = services.billing.bill(hotel.rita, r.id)
    assert bill.total == DT(72)
    services.billing.record_payment(hotel.rita, r.id, amount=DT(72), method=PaymentMethod.CARD)
    assert services.billing.bill(hotel.rita, r.id).balance.is_zero()

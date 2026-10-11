"""Check-out and invoices (story 4.7, BR22)."""

import sqlite3
from datetime import timedelta

import pytest

from hotel.domain.billing import PaymentMethod, PercentDiscount
from hotel.domain.errors import InvalidStateTransitionError, StaleDataError
from hotel.domain.money import Money
from hotel.domain.reservations import ReservationStatus
from hotel.domain.rooms import Housekeeping
from hotel.domain.taxes import PercentTax
from hotel.persistence.repositories.invoices import InvoiceRepository
from tests.integration.test_booking import book, stay

DT = Money.from_dinars
CASH = PaymentMethod.CASH


def _in_house(services, hotel, period=None, number="204", guest=None):
    r = book(services, hotel, period or stay(8, 11), number, guest=guest)
    return services.reservations.check_in(hotel.rita, r.id, version=r.version)


def test_scenario_4_5_check_out_issues_the_final_invoice(services, hotel, clock):
    services.hotel_settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    r = _in_house(services, hotel)  # 3 x 180
    breakfast = services.extras.create(hotel.boss, name="Breakfast", unit_price=DT(15))
    services.extras.charge(hotel.rita, r.id, extra_id=breakfast.id, quantity=2)
    services.billing.grant_discount(
        hotel.boss, PercentDiscount(reservation_id=r.id, reason="Loyal guest", rate_bp=1000)
    )
    services.billing.record_payment(hotel.rita, r.id, amount=DT(200), method=CASH)
    clock.advance(timedelta(days=3))
    preview = services.billing.bill(hotel.rita, r.id)
    invoice = services.invoices.check_out(hotel.rita, r.id, version=r.version)
    assert invoice.number == "F-2026-00001"
    assert invoice.lines == preview.lines  # the final statement includes the services
    assert (invoice.total, invoice.balance) == (preview.total, preview.balance)
    assert invoice.guest_name == "Amira Ben Salah"
    stored = services.reservations.get(hotel.rita, r.id)
    assert stored.status is ReservationStatus.CHECKED_OUT
    assert stored.checked_out_at == clock.now()
    room = services.rooms.get_room(hotel.rita, hotel.rooms["204"].id).room
    assert room.housekeeping is Housekeeping.DIRTY
    assert services.invoices.for_reservation(hotel.rita, r.id) == invoice


def test_numbers_are_sequential_and_a_failure_leaves_no_gap(services, hotel, monkeypatch):
    a = _in_house(services, hotel, stay(8, 9), "204")
    b = _in_house(services, hotel, stay(8, 9), "205", guest=hotel.karim)
    c = _in_house(services, hotel, stay(8, 9), "101")
    assert services.invoices.check_out(hotel.rita, a.id, version=a.version).number == "F-2026-00001"

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(InvoiceRepository, "add", broken)
    with pytest.raises(sqlite3.OperationalError):
        services.invoices.check_out(hotel.rita, b.id, version=b.version)
    assert services.reservations.get(hotel.rita, b.id).status is ReservationStatus.CHECKED_IN
    monkeypatch.undo()
    assert services.invoices.check_out(hotel.rita, b.id, version=b.version).number == "F-2026-00002"
    assert services.invoices.check_out(hotel.rita, c.id, version=c.version).number == "F-2026-00003"


def test_issued_invoices_never_change(services, hotel, clock):
    vat = services.hotel_settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    r = _in_house(services, hotel, stay(8, 9))
    invoice = services.invoices.check_out(hotel.rita, r.id, version=r.version)
    # Later changes to rates, taxes and names leave the invoice as issued.
    services.hotel_settings.update_tax_rule(
        hotel.boss, vat.id, PercentTax(name="VAT", rate_bp=1900, version=vat.version)
    )
    room = hotel.rooms["204"]
    services.rooms.update_room(
        hotel.boss,
        room.id,
        version=room.version,
        number="204",
        category_id=room.category_id,
        capacity=2,
        nightly_rate=DT(999),
        in_service=True,
    )
    again = services.invoices.get(hotel.rita, invoice.id)
    assert again.lines == invoice.lines
    assert again.total == DT(180) + Money(12_600)
    with services.uow_factory() as uow:
        conn = uow.invoices._conn
        for sql in (
            "UPDATE invoice SET total_mill = 0",
            "DELETE FROM invoice",
            "UPDATE invoice_line SET amount_mill = 0",
            "DELETE FROM invoice_line",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                conn.execute(sql)


def test_early_departure_releases_the_unused_nights(services, hotel, clock):
    r = _in_house(services, hotel, stay(8, 12))  # 4 nights booked
    clock.advance(timedelta(days=2))  # leaves on 10 July
    ending, bill, early = services.invoices.preview_check_out(hotel.rita, r.id)
    assert ending.period == stay(8, 10)
    assert early
    assert bill.accommodation == DT(360)
    assert services.reservations.get(hotel.rita, r.id).period == stay(
        8, 12
    )  # preview saves nothing
    invoice = services.invoices.check_out(hotel.rita, r.id, version=r.version)
    assert invoice.departure == stay(8, 10).departure
    assert invoice.total == DT(360)
    with services.uow_factory() as uow:
        actions = [e.action for e in uow.audit.iterate()][-2:]
    assert actions == ["reservation.checked_out", "invoice.issued"]
    # 10 and 11 July can be sold again.
    assert book(services, hotel, stay(10, 12), "204", guest=hotel.karim)


def test_check_out_needs_a_guest_in_the_house_and_the_current_version(services, hotel):
    r = book(services, hotel, stay(8, 10), "204")
    with pytest.raises(InvalidStateTransitionError):
        services.invoices.check_out(hotel.rita, r.id, version=r.version)
    r = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    with pytest.raises(StaleDataError):
        services.invoices.check_out(hotel.rita, r.id, version=r.version - 1)


def test_later_payments_settle_an_unpaid_invoice(services, hotel, clock):
    r = _in_house(services, hotel, stay(8, 9))
    invoice = services.invoices.check_out(hotel.rita, r.id, version=r.version)
    assert invoice.balance == DT(180)
    assert services.front_desk.day(hotel.rita).unpaid == [
        (r.id, invoice.number, "Amira Ben Salah", DT(180))
    ]
    clock.advance(timedelta(hours=1))
    services.billing.record_payment(hotel.rita, r.id, amount=DT(180), method=CASH)
    assert services.front_desk.day(hotel.rita).unpaid == []
    assert services.invoices.get(hotel.rita, invoice.id).balance == DT(180)  # as issued


def test_a_cancellation_fee_is_invoiced_and_a_free_cancellation_is_not(services, hotel):
    late = book(services, hotel, stay(9, 11), "204")  # inside 48 h: 72 DT fee
    services.reservations.cancel(hotel.rita, late.id, version=late.version)
    invoice = services.invoices.for_reservation(hotel.rita, late.id)
    assert invoice.total == DT(72)
    early = book(services, hotel, stay(20, 21), "205")
    services.reservations.cancel(hotel.rita, early.id, version=early.version)
    assert services.invoices.for_reservation(hotel.rita, early.id) is None


def test_a_no_show_fee_is_invoiced(services, hotel, clock):
    r = book(services, hotel, stay(8, 9), "204")
    clock.advance(timedelta(hours=2))
    services.reservations.record_no_show(hotel.rita, r.id, version=r.version)
    assert services.invoices.for_reservation(hotel.rita, r.id).total == DT(36)


def test_dashboard_shows_what_guests_in_the_house_owe(services, hotel):
    r = _in_house(services, hotel, stay(8, 10))  # 360 DT
    services.billing.record_payment(hotel.rita, r.id, amount=DT(60), method=CASH)
    assert services.front_desk.day(hotel.rita).in_house_due == DT(300)


def test_invoice_search(services, hotel):
    r = _in_house(services, hotel, stay(8, 9))
    services.invoices.check_out(hotel.rita, r.id, version=r.version)
    from hotel.domain.paging import PageRequest

    found = services.invoices.search(hotel.rita, "ben sal", PageRequest())
    assert [i.number for i in found.items] == ["F-2026-00001"]
    assert found.items[0].listed_total == DT(180)
    assert services.invoices.search(hotel.rita, "nobody", PageRequest()).total == 0

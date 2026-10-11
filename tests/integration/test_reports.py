"""Management statistics against a real database (story 5.1, brief §4.8)."""

from datetime import date, timedelta

import pytest

from hotel.domain.billing import PaymentMethod
from hotel.domain.errors import PermissionDeniedError, ValidationError
from hotel.domain.money import Money
from tests.integration.test_booking import book, stay

DT = Money.from_dinars


@pytest.fixture
def week(services, hotel, clock):
    """8-10 July: one stay in 204 (2 nights, paid, checked out), one late
    cancellation in 205 (72 DT fee), room 101 closed on the night of the 9th."""
    a = book(services, hotel, stay(8, 10), "204")
    a = services.reservations.check_in(hotel.rita, a.id, version=a.version)
    b = book(services, hotel, stay(9, 11), "205", guest=hotel.karim)
    services.reservations.cancel(hotel.rita, b.id, version=b.version)
    services.rooms.schedule_maintenance(
        hotel.boss,
        hotel.rooms["101"].id,
        first_night=date(2026, 7, 9),
        reopens_on=date(2026, 7, 10),
        reason="Paint",
    )
    clock.advance(timedelta(days=2))  # 10 July
    services.billing.record_payment(hotel.rita, a.id, amount=DT(360), method=PaymentMethod.CASH)
    services.invoices.check_out(hotel.rita, a.id, version=a.version)
    return services.reports.report(hotel.boss, date(2026, 7, 8), date(2026, 7, 10))


def test_occupancy_excludes_maintenance(week):
    assert [(d.night.day, d.sold, d.sellable) for d in week.days] == [
        (8, 1, 4),
        (9, 1, 3),  # 101 closed: 3 rooms could be sold
        (10, 0, 4),
    ]
    assert (week.nights_sold, week.nights_sellable) == (2, 11)
    assert week.occupancy_bp == 1818  # 18.18 %


def test_room_value_adr_and_revpar(week):
    assert week.room_value == DT(360)
    assert week.adr == DT(180)
    assert week.revpar == Money(32_727)  # 360 / 11, half-up


def test_revenue_counts_when_invoiced_and_cash_separately(week):
    assert week.invoices == 2  # the stay and the cancellation fee
    assert week.accommodation == DT(360)
    assert week.fees == DT(72)
    assert week.services.is_zero()
    assert week.taxes.is_zero()
    assert week.revenue == DT(432)
    assert week.cash == {"CASH": DT(360)}
    assert week.cash_received == DT(360)


def test_activity_counts(week):
    assert week.reservations_made == 2
    assert (week.cancellations.count, week.cancellations.fees) == (1, DT(72))
    assert week.no_shows.count == 0
    assert [(c.name, c.nights, c.room_value) for c in week.categories] == [("Deluxe", 2, DT(360))]


def test_outstanding_balances(week):
    assert [(number, due) for _, number, _, due in week.unpaid] == [("F-2026-00001", DT(72))]
    assert week.outstanding == DT(72)


def test_availability_by_category(week):
    assert week.availability_day == date(2026, 7, 10)
    rows = {a.name: (a.rooms, a.maintenance, a.sold, a.free) for a in week.availability}
    assert rows == {"Deluxe": (2, 0, 0, 2), "Standard": (1, 0, 0, 1), "Suite": (1, 0, 0, 1)}


def test_monthly_totals(services, hotel):
    book(services, hotel, stay(30, 31), "204")  # the night of 30 July
    report = services.reports.report(hotel.boss, date(2026, 7, 1), date(2026, 8, 31))
    months = report.months()
    assert [(m.month, m.sold) for m in months] == [(date(2026, 7, 1), 1), (date(2026, 8, 1), 0)]
    assert months[0].sellable == 31 * 4


def test_range_rules_and_access(services, hotel):
    with pytest.raises(ValidationError, match="range_reversed"):
        services.reports.report(hotel.boss, date(2026, 7, 10), date(2026, 7, 9))
    with pytest.raises(ValidationError, match="range_too_long"):
        services.reports.report(hotel.boss, date(2026, 1, 1), date(2028, 1, 2))  # 732 nights
    assert (
        len(services.reports.report(hotel.boss, date(2026, 1, 1), date(2027, 12, 31)).days) == 730
    )
    with pytest.raises(PermissionDeniedError):
        services.reports.report(hotel.rita, date(2026, 7, 1), date(2026, 7, 2))
    assert services.reports.default_range() == (date(2026, 7, 1), date(2026, 7, 31))


def test_empty_hotel_reports_zero_without_dividing_by_zero(services, manager):
    from hotel.domain.actor import Actor

    report = services.reports.report(Actor(manager), date(2026, 7, 1), date(2026, 7, 7))
    assert (report.occupancy_bp, report.adr, report.revpar) == (0, Money(0), Money(0))

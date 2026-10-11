"""Seasonal and weekend prices against the booking flow (story 5.6)."""

from datetime import date

import pytest

from hotel.domain.errors import ConflictError, PermissionDeniedError, ValidationError
from hotel.domain.money import Money
from hotel.domain.reservations import RoomRequest
from hotel.domain.settings import HotelSettings
from tests.integration.test_booking import book, stay

DT = Money.from_dinars


def _summer(services, hotel, actor=None, **changes):
    fields = {
        "category_id": hotel.rooms["204"].category_id,
        "name": "Summer",
        "first_night": date(2026, 7, 10),
        "last_night": date(2026, 7, 11),
        "nightly_rate": DT(250),
        **changes,
    }
    return services.rooms.add_rate_period(actor or hotel.boss, **fields)


def test_bookings_use_periods_then_weekend_then_base(services, hotel):
    services.hotel_settings.update(hotel.boss, HotelSettings(weekend_surcharge_bp=1000))
    _summer(services, hotel)  # Deluxe, nights of 10 and 11 July
    r = book(services, hotel, stay(9, 14), "204")  # Thu 9 .. Mon 13 nights
    assert [n.rate for n in r.nights] == [DT(180), DT(250), DT(250), DT(198), DT(180)]
    #                                      Thu       Fri(period) Sat(period) Sun(weekend) Mon


def test_existing_bookings_keep_their_prices(services, hotel):
    r = book(services, hotel, stay(10, 12), "204")
    period = _summer(services, hotel)
    assert services.reservations.get(hotel.rita, r.id).accommodation_total == DT(360)
    # A change keeps the booked nights' prices; only the added night uses the period.
    _, quote = services.reservations.preview_change(
        hotel.rita, r.id, period=stay(9, 12), rooms=[RoomRequest(hotel.rooms["204"].id, 1)]
    )
    assert [n.rate for n in quote.lines[0].nights] == [DT(180), DT(180), DT(180)]
    services.rooms.delete_rate_period(hotel.boss, period.id)
    assert services.rooms.rate_periods(hotel.rita) == []


def test_periods_cannot_overlap_within_a_category(services, hotel):
    _summer(services, hotel)
    with pytest.raises(ConflictError, match="overlap"):
        _summer(services, hotel, first_night=date(2026, 7, 11), last_night=date(2026, 7, 15))
    _summer(
        services, hotel, first_night=date(2026, 7, 12), last_night=date(2026, 7, 15)
    )  # next day: fine
    other = hotel.rooms["101"].category_id
    _summer(services, hotel, category_id=other)  # another category: fine


def test_rate_period_rules(services, hotel):
    with pytest.raises(PermissionDeniedError):
        _summer(services, hotel, actor=hotel.rita)
    with pytest.raises(ValidationError, match="dates_reversed"):
        _summer(services, hotel, last_night=date(2026, 7, 1))
    with pytest.raises(ValidationError, match="category_unknown"):
        _summer(services, hotel, category_id=999)

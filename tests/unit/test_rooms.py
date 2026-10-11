from datetime import date

import pytest

from hotel.domain.errors import ValidationError
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.rooms import (
    MaintenancePeriod,
    Room,
    validate_capacity,
    validate_category_name,
    validate_nightly_rate,
    validate_room_number,
    validate_text,
)


@pytest.mark.parametrize(("raw", "number"), [("204", "204"), (" b-12 ", "B-12"), ("ａ1", "A1")])
def test_room_numbers_are_normalised(raw, number):
    assert validate_room_number(raw) == number


@pytest.mark.parametrize("raw", ["", "-1", "12 3", "ROOM-NUMBER-X", "2'04", "<b>"])
def test_invalid_room_numbers(raw):
    with pytest.raises(ValidationError):
        validate_room_number(raw)


def test_capacity_and_rate_limits():
    assert validate_capacity(1) == 1
    for bad in (0, 11, -3):
        with pytest.raises(ValidationError):
            validate_capacity(bad)
    assert validate_nightly_rate(Money.from_dinars(180)) == Money(180_000)
    for bad in (Money(0), Money(-1), Money.from_dinars(100_001)):
        with pytest.raises(ValidationError):
            validate_nightly_rate(bad)


def test_names_and_texts():
    assert validate_category_name("  Deluxe   sea  view ") == "Deluxe sea view"
    with pytest.raises(ValidationError):
        validate_category_name("   ")
    assert validate_text(" ok ", "notes", max_length=10) == "ok"
    with pytest.raises(ValidationError):
        validate_text("x" * 11, "notes", max_length=10)
    with pytest.raises(ValidationError):
        validate_text("  ", "reason", max_length=10, required=True)


def test_room_capacity_rule():
    room = Room(1, "204", 1, 2, Money(180_000))
    assert room.can_host(2)
    assert not room.can_host(3)
    assert not room.can_host(0)


def test_maintenance_dates():
    m = MaintenancePeriod(1, 1, StayPeriod(date(2026, 7, 10), date(2026, 7, 13)), "Paint")
    assert m.first_night == date(2026, 7, 10)
    assert m.last_night == date(2026, 7, 12)
    assert m.reopens_on == date(2026, 7, 13)

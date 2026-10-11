"""Seasonal and weekend prices (story 5.6)."""

from datetime import date

import pytest

from hotel.domain.errors import ValidationError
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.pricing import Pricing, RatePeriod, validate_rate_period
from hotel.domain.rooms import Room

DELUXE = Room(1, "204", category_id=7, capacity=2, nightly_rate=Money.from_dinars(180))
SUMMER = RatePeriod(
    1, 7, "Summer", StayPeriod(date(2026, 7, 10), date(2026, 7, 20)), Money.from_dinars(250)
)
FRIDAY, SATURDAY, SUNDAY = date(2026, 7, 3), date(2026, 7, 4), date(2026, 7, 5)


def test_base_rate_without_any_rule():
    assert Pricing().rate_for(DELUXE, SATURDAY) == Money.from_dinars(180)


def test_weekend_surcharge_on_the_chosen_nights_only():
    pricing = Pricing(weekend_nights=frozenset({5, 6}), weekend_surcharge_bp=1000)
    assert pricing.rate_for(DELUXE, SATURDAY) == Money.from_dinars(198)
    assert pricing.rate_for(DELUXE, SUNDAY) == Money.from_dinars(198)
    assert pricing.rate_for(DELUXE, FRIDAY) == Money.from_dinars(180)


def test_a_period_beats_the_weekend_and_only_for_its_category_and_nights():
    pricing = Pricing((SUMMER,), frozenset({5, 6}), 1000)
    assert pricing.rate_for(DELUXE, date(2026, 7, 11)) == Money.from_dinars(250)  # a Saturday
    assert pricing.rate_for(DELUXE, date(2026, 7, 20)) == Money.from_dinars(180)  # day after
    other = Room(2, "101", category_id=8, capacity=2, nightly_rate=Money.from_dinars(120))
    assert pricing.rate_for(other, date(2026, 7, 12)) == Money.from_dinars(132)  # weekend


def test_rate_period_validation():
    assert validate_rate_period("  Summer  2026 ", SUMMER.period, Money(1)) == "Summer 2026"
    with pytest.raises(ValidationError):
        validate_rate_period("", SUMMER.period, Money(1))
    with pytest.raises(ValidationError):
        validate_rate_period("x", StayPeriod(date(2026, 1, 1), date(2027, 1, 3)), Money(1))
    with pytest.raises(ValidationError):
        validate_rate_period("x", SUMMER.period, Money(0))

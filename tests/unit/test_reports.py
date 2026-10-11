from datetime import date

import pytest

from hotel.domain.errors import ValidationError
from hotel.domain.money import Money
from hotel.domain.reports import (
    MAX_RANGE_DAYS,
    average,
    nights_between,
    rate_bp,
    validate_range,
)


def test_range_is_inclusive_and_capped_at_two_years():
    first = date(2026, 1, 1)
    assert validate_range(first, first) == (first, first)
    last = date.fromordinal(first.toordinal() + MAX_RANGE_DAYS - 1)
    assert len(nights_between(*validate_range(first, last))) == MAX_RANGE_DAYS
    with pytest.raises(ValidationError, match="too_long"):
        validate_range(first, date.fromordinal(last.toordinal() + 1))
    with pytest.raises(ValidationError, match="reversed"):
        validate_range(first, date(2025, 12, 31))


def test_rates_round_down_and_never_divide_by_zero():
    assert rate_bp(2, 11) == 1818
    assert rate_bp(3, 4) == 7500
    assert rate_bp(5, 0) == 0


def test_average_rounds_half_up_to_the_millime():
    assert average(Money(360_000), 11) == Money(32_727)  # 32727.27
    assert average(Money(5), 2) == Money(3)  # 2.5 -> 3, not banker's 2
    assert average(Money(100), 0) == Money(0)

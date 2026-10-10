from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hotel.domain.errors import ValidationError
from hotel.domain.money import Money


@pytest.mark.parametrize(
    ("text", "millimes"),
    [("180", 180_000), ("180.5", 180_500), ("180.500", 180_500), ("0.001", 1), (" 42 ", 42_000)],
)
def test_parse_valid_amounts(text, millimes):
    assert Money.parse(text) == Money(millimes)


@pytest.mark.parametrize("text", ["", "-5", "1.2345", "1e3", "12,5", "abc", "1 000", ".5", "5."])
def test_parse_rejects_invalid_amounts(text):
    with pytest.raises(ValidationError) as caught:
        Money.parse(text)
    assert caught.value.code == "money.invalid"


def test_floats_and_bools_are_refused():
    with pytest.raises(TypeError):
        Money(1.5)
    with pytest.raises(TypeError):
        Money(True)
    with pytest.raises(TypeError):
        Money.from_dinars(0.1)
    with pytest.raises(TypeError):
        Money(1000).times(1.5)


def test_from_dinars():
    assert Money.from_dinars(180) == Money(180_000)
    assert Money.from_dinars(Decimal("0.125")) == Money(125)
    with pytest.raises(ValidationError):
        Money.from_dinars(Decimal("0.0001"))


def test_arithmetic():
    assert Money(150_000).times(3) + Money(80_000) - Money(100_000) == Money(430_000)
    assert -Money(5) == Money(-5)
    assert Money(3) > Money(2)


def test_adding_a_number_is_a_type_error():
    with pytest.raises(TypeError):
        Money(1) + 1
    with pytest.raises(TypeError):
        Money(1) - 1


@pytest.mark.parametrize(
    ("millimes", "basis_points", "expected"),
    [
        (1, 5000, 1),  # 0.5 rounds up (banker's rounding would give 0)
        (3, 5000, 2),  # 1.5 rounds up
        (5, 5000, 3),  # 2.5 rounds up (banker's rounding would give 2)
        (-1, 5000, -1),  # half away from zero for negatives
        (180_000, 700, 12_600),  # 7 % of 180 DT
        (450_000, 2000, 90_000),  # 20 % cancellation fee on 450 DT
    ],
)
def test_percent_rounds_half_up(millimes, basis_points, expected):
    assert Money(millimes).percent(basis_points) == Money(expected)


@pytest.mark.parametrize(
    ("millimes", "text"), [(180_500, "180.500"), (5, "0.005"), (-1_250, "-1.250"), (0, "0.000")]
)
def test_str(millimes, text):
    assert str(Money(millimes)) == text


def test_queries():
    assert Money.zero().is_zero()
    assert Money(-1).is_negative()
    assert Money(180_500).to_decimal() == Decimal("180.500")


@given(st.integers(min_value=0, max_value=999_999_999_999))
def test_parse_and_str_round_trip(millimes):
    assert Money.parse(str(Money(millimes))) == Money(millimes)

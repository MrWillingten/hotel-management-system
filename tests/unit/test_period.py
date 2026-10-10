"""StayPeriod: the half-open date range at the heart of double-booking prevention."""

from datetime import date, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hotel.domain.errors import ValidationError
from hotel.domain.period import StayPeriod


def period(a: int, d: int) -> StayPeriod:
    """July a to July d."""
    return StayPeriod(date(2026, 7, a), date(2026, 7, d))


def test_nights_and_each_night():
    stay = period(10, 15)
    assert stay.nights == 5
    assert list(stay.each_night()) == [date(2026, 7, day) for day in range(10, 15)]


def test_departure_must_be_after_arrival():
    with pytest.raises(ValidationError) as caught:
        period(10, 10)
    assert caught.value.fields == {"departure": "period.departure_not_after_arrival"}
    with pytest.raises(ValidationError):
        period(15, 10)


def test_datetimes_are_refused():
    with pytest.raises(TypeError):
        StayPeriod(datetime(2026, 7, 10), date(2026, 7, 12))  # noqa: DTZ001
    with pytest.raises(TypeError):
        StayPeriod("2026-07-10", date(2026, 7, 12))


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((10, 15), (12, 14), True),  # PDF scenario §4.3: 12-14 July inside 10-15 July
        ((10, 15), (15, 18), False),  # same-day turnover: departure day is free
        ((15, 18), (10, 15), False),
        ((10, 15), (14, 16), True),  # one shared night
        ((10, 15), (8, 11), True),
        ((10, 15), (10, 15), True),  # identical
        ((10, 15), (5, 20), True),  # contains
        ((10, 11), (11, 12), False),  # adjacent one-night stays
        ((10, 12), (20, 25), False),
    ],
)
def test_overlap_boundaries(first, second, expected):
    assert period(*first).overlaps(period(*second)) is expected


def test_contains_uses_the_night_convention():
    stay = period(10, 15)
    assert stay.contains(date(2026, 7, 10))
    assert stay.contains(date(2026, 7, 14))
    assert not stay.contains(date(2026, 7, 15))  # the guest leaves that morning
    assert not stay.contains(date(2026, 7, 9))


# ------------------------------------------------------------ property-based tests
# Hypothesis generates hundreds of random stays and checks rules that must hold
# for every one of them, including edge cases nobody thought to write down.

_day = st.dates(min_value=date(2026, 1, 1), max_value=date(2027, 12, 31))
_length = st.integers(min_value=1, max_value=60)
_stays = st.builds(lambda a, n: StayPeriod(a, a + timedelta(days=n)), _day, _length)


@given(_stays, _stays)
def test_overlap_is_symmetric(a, b):
    assert a.overlaps(b) == b.overlaps(a)


@given(_stays, _stays)
def test_overlap_means_sharing_at_least_one_night(a, b):
    shared_nights = set(a.each_night()) & set(b.each_night())
    assert a.overlaps(b) == bool(shared_nights)


@given(_stays, _length)
def test_back_to_back_stays_never_overlap(a, n):
    following = StayPeriod(a.departure, a.departure + timedelta(days=n))
    assert not a.overlaps(following)


@given(_stays)
def test_a_stay_overlaps_itself_and_counts_its_nights(a):
    assert a.overlaps(a)
    assert a.nights == len(list(a.each_night()))

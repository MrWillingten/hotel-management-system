from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from hotel.domain.errors import BusinessRuleViolation, InvalidStateTransitionError, ValidationError
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import (
    ALLOWED_TRANSITIONS,
    CancellationPolicy,
    Reservation,
    ReservationStatus,
    RoomNight,
    RoomRequest,
    reservation_code,
    validate_room_requests,
    validate_stay,
)

TUNIS = ZoneInfo("Africa/Tunis")
TODAY = date(2026, 7, 8)


def _reservation(arrival=date(2026, 7, 10), nights=3, rate=150_000, created=None):
    period = StayPeriod(arrival, arrival + timedelta(days=nights))
    return Reservation(
        id=1,
        code="R-2026-00001",
        guest_id=1,
        period=period,
        nights=[RoomNight(1, n, Money(rate)) for n in period.each_night()],
        created_at=created or datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_codes():
    assert reservation_code(2026, 1) == "R-2026-00001"
    assert reservation_code(2027, 12345) == "R-2027-12345"


def test_accommodation_total_is_the_sum_of_locked_nights():
    """§4.7 example: three nights at 150 DT."""
    assert _reservation().accommodation_total == Money.from_dinars(450)


@pytest.mark.parametrize("status", list(ReservationStatus))
def test_every_transition(status):
    for target in ReservationStatus:
        reservation = _reservation()
        reservation.status = status
        if target in ALLOWED_TRANSITIONS[status]:
            reservation.transition(target)
            assert reservation.status is target
        else:
            with pytest.raises(InvalidStateTransitionError):
                reservation.transition(target)


def test_active_statuses():
    active = {s for s in ReservationStatus if s.is_active}
    assert active == {ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN}


def test_stay_limits():
    validate_stay(StayPeriod(TODAY, TODAY + timedelta(days=60)), TODAY)
    with pytest.raises(ValidationError, match="arrival_in_past"):
        validate_stay(StayPeriod(TODAY - timedelta(days=1), TODAY + timedelta(days=1)), TODAY)
    with pytest.raises(ValidationError, match="too_long"):
        validate_stay(StayPeriod(TODAY, TODAY + timedelta(days=61)), TODAY)
    far = TODAY + timedelta(days=731)
    with pytest.raises(ValidationError, match="too_far"):
        validate_stay(StayPeriod(far, far + timedelta(days=1)), TODAY)


def test_room_request_limits():
    validate_room_requests([RoomRequest(1, 2, 1)])
    for bad, code in (
        ([], "rooms_count"),
        ([RoomRequest(i, 1) for i in range(11)], "rooms_count"),
        ([RoomRequest(1, 1), RoomRequest(1, 2)], "room_twice"),
        ([RoomRequest(1, 0, 2)], "occupants_invalid"),
        ([RoomRequest(1, 1, -1)], "occupants_invalid"),
    ):
        with pytest.raises(ValidationError, match=code):
            validate_room_requests(bad)


# ------------------------------------------------------------ BR11 cancellation fee
POLICY = CancellationPolicy()
ARRIVAL_14H = datetime(2026, 7, 10, 14, 0, tzinfo=TUNIS)  # arrival day at check-in time


@pytest.mark.parametrize(
    ("before_arrival", "fee"),
    [
        (timedelta(hours=48, minutes=1), 0),  # 48:01 before: free
        (timedelta(hours=48), 0),  # exactly 48:00: "less than 48 h" is not met, free
        (timedelta(hours=47, minutes=59), 90_000),  # 47:59: 20 % of 450 DT
        (timedelta(minutes=1), 90_000),
    ],
)
def test_fee_boundaries(before_arrival, fee):
    assert POLICY.fee_for(_reservation(), ARRIVAL_14H - before_arrival, TUNIS) == Money(fee)


def test_cancelling_after_arrival_time_is_refused():
    with pytest.raises(BusinessRuleViolation, match="cancel_after_arrival"):
        POLICY.fee_for(_reservation(), ARRIVAL_14H, TUNIS)


def test_free_until_and_arrival_instant():
    assert POLICY.arrival_instant(date(2026, 7, 10), TUNIS) == ARRIVAL_14H
    assert POLICY.free_until(_reservation(), TUNIS) == ARRIVAL_14H - timedelta(hours=48)


def test_grace_period():
    booked = ARRIVAL_14H - timedelta(hours=10)
    reservation = _reservation(created=booked)
    graceful = CancellationPolicy(grace_period=timedelta(minutes=30))
    assert graceful.fee_for(reservation, booked + timedelta(minutes=20), TUNIS).is_zero()
    assert not graceful.fee_for(reservation, booked + timedelta(minutes=40), TUNIS).is_zero()
    assert not POLICY.fee_for(reservation, booked, TUNIS).is_zero()  # default: no grace


# ---------------------------------------------------------------- check-in and no-show
NOW = datetime(2026, 7, 10, 9, 0, tzinfo=UTC)


def test_check_in_on_the_arrival_day_or_later_during_the_stay():
    for day in (date(2026, 7, 10), date(2026, 7, 12)):  # on time, or two days late
        r = _reservation()
        r.check_in(NOW, day)
        assert r.status is ReservationStatus.CHECKED_IN
        assert r.checked_in_at == NOW


def test_check_in_before_arrival_or_after_the_stay_is_refused():
    r = _reservation()
    with pytest.raises(BusinessRuleViolation, match="check_in_too_early"):
        r.check_in(NOW, date(2026, 7, 9))
    with pytest.raises(BusinessRuleViolation, match="check_in_too_late"):
        r.check_in(NOW, date(2026, 7, 13))  # the departure day
    assert r.status is ReservationStatus.CONFIRMED


def test_check_in_only_from_confirmed():
    r = _reservation()
    r.check_in(NOW, date(2026, 7, 10))
    with pytest.raises(InvalidStateTransitionError):
        r.check_in(NOW, date(2026, 7, 10))


def test_no_show_is_charged_like_a_late_cancellation_after_the_arrival_time():
    policy = CancellationPolicy()
    r = _reservation(nights=3, rate=150_000)
    arrival = datetime(2026, 7, 10, 13, 0, tzinfo=UTC)  # 14:00 in Tunis
    with pytest.raises(BusinessRuleViolation, match="no_show_too_early"):
        policy.no_show_fee(r, arrival - timedelta(seconds=1), TUNIS)
    assert policy.no_show_fee(r, arrival, TUNIS) == Money.from_dinars(90)  # 20 % of 450


# ---------------------------------------------------------------- check-out
def _in_house(arrival=date(2026, 7, 10), nights=3):
    r = _reservation(arrival=arrival, nights=nights)
    r.check_in(NOW, arrival)
    return r


def test_check_out_on_the_planned_day_keeps_every_night():
    r = _in_house()
    assert r.check_out(NOW, date(2026, 7, 13)) is False
    assert r.status is ReservationStatus.CHECKED_OUT
    assert r.checked_out_at == NOW
    assert len(r.nights) == 3


def test_early_departure_charges_only_the_nights_stayed():
    r = _in_house()
    assert r.check_out(NOW, date(2026, 7, 12)) is True
    assert r.period == StayPeriod(date(2026, 7, 10), date(2026, 7, 12))
    assert r.accommodation_total == Money.from_dinars(300)


def test_leaving_on_the_arrival_day_still_pays_one_night():
    r = _in_house()
    r.check_out(NOW, date(2026, 7, 10))
    assert r.period.nights == 1
    assert r.accommodation_total == Money.from_dinars(150)


def test_a_late_check_out_changes_nothing_and_only_from_checked_in():
    r = _in_house()
    assert r.check_out(NOW, date(2026, 7, 15)) is False
    assert r.period.departure == date(2026, 7, 13)
    with pytest.raises(InvalidStateTransitionError):
        _reservation().check_out(NOW, date(2026, 7, 10))


def test_invoice_numbers():
    from hotel.domain.invoices import invoice_number

    assert invoice_number(2026, 1) == "F-2026-00001"

from datetime import UTC, date, datetime, timedelta

import pytest

from hotel.domain.errors import (
    BusinessRuleViolation,
    InvalidStateTransitionError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.reservations import ReservationStatus, RoomRequest
from hotel.services.reservations import RoomUnavailableError
from tests.integration.test_booking import book, stay


def _requests(hotel, *pairs):
    return [RoomRequest(hotel.rooms[number].id, adults) for number, adults in pairs]


def test_scenario_4_4_extend_from_three_to_five_nights(services, hotel):
    r = book(services, hotel, stay(10, 13), "204")
    changed = services.reservations.modify(
        hotel.rita, r.id, version=r.version, period=stay(10, 15), rooms=_requests(hotel, ("204", 1))
    )
    assert changed.period.nights == 5
    assert changed.accommodation_total == Money.from_dinars(5 * 180)


def test_extension_is_refused_when_the_room_is_taken(services, hotel):
    r = book(services, hotel, stay(10, 13), "204")
    book(services, hotel, stay(14, 16), "204", guest=hotel.karim)
    with pytest.raises(RoomUnavailableError) as caught:
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=r.version,
            period=stay(10, 15),
            rooms=_requests(hotel, ("204", 1)),
        )
    assert caught.value.params["first"] == "2026-07-14"
    unchanged = services.reservations.get(hotel.rita, r.id)
    assert unchanged.period == stay(10, 13)  # nothing saved


def test_kept_nights_keep_their_price_and_new_nights_use_todays_rate(services, hotel):
    r = book(services, hotel, stay(10, 12), "204")  # 2 x 180
    room = hotel.rooms["204"]
    services.rooms.update_room(
        hotel.boss,
        room.id,
        version=room.version,
        number="204",
        category_id=room.category_id,
        capacity=2,
        nightly_rate=Money.from_dinars(200),
        in_service=True,
    )
    _, quote = services.reservations.preview_change(
        hotel.rita, r.id, period=stay(10, 14), rooms=_requests(hotel, ("204", 1))
    )
    assert [n.rate for n in quote.lines[0].nights] == [Money(180_000)] * 2 + [Money(200_000)] * 2
    changed = services.reservations.modify(
        hotel.rita, r.id, version=r.version, period=stay(10, 14), rooms=_requests(hotel, ("204", 1))
    )
    assert changed.accommodation_total == Money.from_dinars(760)


def test_move_dates_and_rooms(services, hotel):
    r = book(services, hotel, stay(10, 12), "204")
    moved = services.reservations.modify(
        hotel.rita,
        r.id,
        version=r.version,
        period=stay(11, 13),
        rooms=_requests(hotel, ("401", 3), ("101", 1)),
    )
    assert {room.number for room in moved.rooms} == {"401", "101"}
    assert moved.accommodation_total == Money.from_dinars(2 * 320 + 2 * 120)
    # 204 is free again for someone else
    book(services, hotel, stay(10, 12), "204", guest=hotel.karim)
    with services.uow_factory() as uow:
        entry = list(uow.audit.iterate())[-2]
    assert entry.action == "reservation.modified"
    assert entry.details["before"] == "2026-07-10/2026-07-12"


def test_shortening_and_capacity_and_versions(services, hotel):
    r = book(services, hotel, stay(10, 14), "204")
    short = services.reservations.modify(
        hotel.rita, r.id, version=r.version, period=stay(10, 12), rooms=_requests(hotel, ("204", 2))
    )
    assert short.period.nights == 2
    with pytest.raises(StaleDataError):
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=r.version,
            period=stay(10, 11),
            rooms=_requests(hotel, ("204", 1)),
        )
    with pytest.raises(BusinessRuleViolation, match="capacity"):
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=short.version,
            period=stay(10, 12),
            rooms=_requests(hotel, ("204", 3)),
        )
    with pytest.raises(ValidationError, match="arrival_in_past"):
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=short.version,
            period=stay(7, 12),
            rooms=_requests(hotel, ("204", 1)),
        )


def _check_in(services, reservation):
    """Sprint 4 adds check-in; until then the status is set directly for these tests."""
    with services.uow_factory() as uow:
        stored = uow.reservations.get(reservation.id)
        stored.transition(ReservationStatus.CHECKED_IN)
        stored.checked_in_at = services.clock.now()
        uow.reservations.update(stored)
        return stored


def test_checked_in_guests_can_only_change_departure_and_occupants(services, hotel, clock):
    r = book(services, hotel, stay(8, 10), "204")
    r = _check_in(services, r)
    longer = services.reservations.modify(
        hotel.rita, r.id, version=r.version, period=stay(8, 12), rooms=_requests(hotel, ("204", 2))
    )
    assert longer.period.departure == date(2026, 7, 12)
    with pytest.raises(BusinessRuleViolation, match="checked_in_limits"):
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=longer.version,
            period=stay(9, 12),
            rooms=_requests(hotel, ("204", 2)),
        )
    with pytest.raises(BusinessRuleViolation, match="checked_in_limits"):
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=longer.version,
            period=stay(8, 12),
            rooms=_requests(hotel, ("205", 2)),
        )
    clock.advance(timedelta(days=2))
    with pytest.raises(ValidationError, match="departure_in_past"):
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=longer.version,
            period=stay(8, 10),
            rooms=_requests(hotel, ("204", 2)),
        )
    with pytest.raises(InvalidStateTransitionError, match="not_cancellable"):
        services.reservations.cancel(hotel.rita, r.id, version=longer.version)


# ------------------------------------------------------------ cancellation (BR11)
def test_cancel_early_is_free_and_releases_the_rooms(services, hotel):
    r = book(services, hotel, stay(20, 23), "204")  # arrival 12 days away
    assert services.reservations.cancellation_fee(hotel.rita, r.id).is_zero()
    cancelled = services.reservations.cancel(hotel.rita, r.id, version=r.version)
    assert cancelled.status is ReservationStatus.CANCELLED
    assert cancelled.cancellation_fee == Money.zero()
    assert cancelled.nights == []
    book(services, hotel, stay(20, 23), "204", guest=hotel.karim)  # room is free again
    with services.uow_factory() as uow:
        assert list(uow.audit.iterate())[-2].details["fee"] == "0.000"


@pytest.mark.parametrize(
    ("now_utc", "fee"),
    [
        # Arrival 10 July at 14:00 in Tunis = 13:00 UTC; 48 h before = 8 July 13:00 UTC.
        (datetime(2026, 7, 8, 12, 59, tzinfo=UTC), 0),  # 48:01 before
        (datetime(2026, 7, 8, 13, 0, tzinfo=UTC), 0),  # exactly 48:00
        (datetime(2026, 7, 8, 13, 1, tzinfo=UTC), 108_000),  # 47:59 -> 20 % of 540 DT
    ],
)
def test_late_cancellation_fee_through_the_service(services, hotel, clock, now_utc, fee):
    r = book(services, hotel, stay(10, 13), "204")
    clock._instant = now_utc
    cancelled = services.reservations.cancel(hotel.rita, r.id, version=r.version)
    assert cancelled.cancellation_fee == Money(fee)


def test_cancelling_after_the_arrival_time_is_refused(services, hotel, clock):
    r = book(services, hotel, stay(10, 13), "204")
    clock._instant = datetime(2026, 7, 10, 13, 0, tzinfo=UTC)  # 14:00 in Tunis
    with pytest.raises(BusinessRuleViolation, match="cancel_after_arrival"):
        services.reservations.cancel(hotel.rita, r.id, version=r.version)


def test_a_cancelled_reservation_is_final(services, hotel):
    r = book(services, hotel, stay(20, 22), "204")
    cancelled = services.reservations.cancel(hotel.rita, r.id, version=r.version)
    with pytest.raises(InvalidStateTransitionError):
        services.reservations.cancel(hotel.rita, r.id, version=cancelled.version)
    with pytest.raises(InvalidStateTransitionError, match="not_modifiable"):
        services.reservations.modify(
            hotel.rita,
            r.id,
            version=cancelled.version,
            period=stay(20, 22),
            rooms=_requests(hotel, ("204", 1)),
        )
    with pytest.raises(StaleDataError):
        services.reservations.cancel(hotel.rita, r.id, version=r.version)

"""Check-in, no-show, housekeeping and the dashboard figures (stories 4.1, 4.2, 4.9)."""

from datetime import timedelta

import pytest

from hotel.domain.errors import (
    BusinessRuleViolation,
    InvalidStateTransitionError,
    PermissionDeniedError,
    StaleDataError,
)
from hotel.domain.money import Money
from hotel.domain.reservations import ReservationStatus
from hotel.domain.rooms import Housekeeping, RoomStatus
from tests.integration.test_booking import book, stay


def test_scenario_4_5_check_in(services, hotel):
    r = book(services, hotel, stay(8, 10), "204")
    checked_in = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    assert checked_in.status is ReservationStatus.CHECKED_IN
    assert checked_in.checked_in_at == services.clock.now()
    assert services.rooms.get_room(hotel.rita, hotel.rooms["204"].id).status is RoomStatus.OCCUPIED


def test_check_in_is_refused_before_the_arrival_day(services, hotel):
    r = book(services, hotel, stay(9, 10), "204")
    with pytest.raises(BusinessRuleViolation, match="check_in_too_early"):
        services.reservations.check_in(hotel.rita, r.id, version=r.version)


def test_check_in_needs_the_current_version(services, hotel):
    r = book(services, hotel, stay(8, 10), "204")
    services.reservations.check_in(hotel.rita, r.id, version=r.version)
    with pytest.raises(StaleDataError):
        services.reservations.check_in(hotel.rita, r.id, version=r.version)


def test_nobody_moves_in_before_the_previous_guest_has_left(services, hotel, clock):
    first = book(services, hotel, stay(8, 9), "204")
    services.reservations.check_in(hotel.rita, first.id, version=first.version)
    second = book(services, hotel, stay(9, 11), "204", guest=hotel.karim)
    clock.advance(timedelta(days=1))  # 9 July: the first guest has not checked out yet
    room = services.rooms.get_room(hotel.rita, hotel.rooms["204"].id)
    assert room.status is RoomStatus.OCCUPIED  # still in the room on the departure day
    with pytest.raises(BusinessRuleViolation, match="room_still_occupied") as caught:
        services.reservations.check_in(hotel.rita, second.id, version=second.version)
    assert caught.value.params == {"room": "204", "code": first.code}


def test_no_show_after_the_arrival_time_releases_the_rooms(services, hotel, clock):
    r = book(services, hotel, stay(8, 11), "204")  # 3 x 180 DT
    # 8 July 13:00 in Tunis: before the 14:00 check-in time
    with pytest.raises(BusinessRuleViolation, match="no_show_too_early"):
        services.reservations.no_show_fee(hotel.rita, r.id)
    clock.advance(timedelta(hours=1))
    assert services.reservations.no_show_fee(hotel.rita, r.id) == Money.from_dinars(108)
    recorded = services.reservations.record_no_show(hotel.rita, r.id, version=r.version)
    assert recorded.status is ReservationStatus.NO_SHOW
    assert recorded.cancellation_fee == Money.from_dinars(108)
    assert recorded.no_show_at == clock.now()
    assert recorded.nights == []
    # The room can be sold again to a walk-in guest the same evening.
    assert book(services, hotel, stay(8, 9), "204", guest=hotel.karim)
    with pytest.raises(InvalidStateTransitionError):
        services.reservations.record_no_show(hotel.rita, r.id, version=recorded.version)


def test_checked_in_guests_cannot_be_no_shows(services, hotel, clock):
    r = book(services, hotel, stay(8, 10), "204")
    r = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    clock.advance(timedelta(hours=2))
    with pytest.raises(InvalidStateTransitionError):
        services.reservations.record_no_show(hotel.rita, r.id, version=r.version)
    assert services.reservations.arrival_has_passed(r.period)


def test_front_desk_actions_are_audited(services, hotel, clock):
    a = book(services, hotel, stay(8, 10), "204")
    b = book(services, hotel, stay(8, 10), "205", guest=hotel.karim)
    services.reservations.check_in(hotel.rita, a.id, version=a.version)
    clock.advance(timedelta(hours=2))
    services.reservations.record_no_show(hotel.rita, b.id, version=b.version)
    with services.uow_factory() as uow:
        actions = [entry.action for entry in uow.audit.iterate()]
    assert "reservation.checked_in" in actions
    assert "reservation.no_show" in actions


def test_housekeeping(services, hotel):
    room = hotel.rooms["101"]
    dirty = services.rooms.set_housekeeping(hotel.rita, room.id, Housekeeping.DIRTY)
    assert dirty.housekeeping is Housekeeping.DIRTY
    assert dirty.version == room.version  # not a change to the room's description
    assert services.rooms.get_room(hotel.rita, room.id).room.housekeeping is Housekeeping.DIRTY
    assert [r.number for r in services.front_desk.day(hotel.rita).to_clean] == ["101"]
    cleaned = services.rooms.set_housekeeping(hotel.rita, room.id, Housekeeping.CLEAN)
    assert services.rooms.get_room(hotel.rita, room.id).room.housekeeping is Housekeeping.CLEAN
    assert [r.number for r in services.front_desk.day(hotel.rita).to_clean] == ["101"]
    assert not cleaned.housekeeping.is_ready  # cleaned, but nobody has inspected it yet
    services.rooms.set_housekeeping(hotel.rita, room.id, Housekeeping.INSPECTED)
    assert services.front_desk.day(hotel.rita).to_clean == []


def test_dashboard_figures(services, hotel, clock):
    arriving = book(services, hotel, stay(8, 10), "204")
    late = book(services, hotel, stay(8, 9), "205", guest=hotel.karim)
    staying = book(services, hotel, stay(8, 9), "401", adults=3)
    tomorrow = book(services, hotel, stay(9, 10), "101")  # not an arrival today
    services.reservations.check_in(hotel.rita, staying.id, version=staying.version)
    day = services.front_desk.day(hotel.rita)
    assert {r.code for r in day.arrivals} == {arriving.code, late.code}
    assert [r.code for r in day.in_house] == [staying.code]
    assert day.guests_in_house == 3
    assert day.departures == []
    assert (day.occupancy.sold, day.occupancy.sellable) == (3, 4)
    assert day.occupancy.basis_points == 7500
    clock.advance(timedelta(days=1))
    day = services.front_desk.day(hotel.rita)
    assert [r.code for r in day.departures] == [staying.code]
    # 204 is still expected (late); 205's one-night stay is over, so it is not listed.
    assert [r.code for r in day.arrivals] == [arriving.code, tomorrow.code]


def test_occupancy_excludes_rooms_under_maintenance(services, hotel):
    services.rooms.schedule_maintenance(
        hotel.boss,
        hotel.rooms["101"].id,
        first_night=stay(8, 9).arrival,
        reopens_on=stay(8, 9).departure,
        reason="Paint",
    )
    book(services, hotel, stay(8, 9), "204")
    occupancy = services.front_desk.day(hotel.rita).occupancy
    assert (occupancy.sold, occupancy.sellable) == (1, 3)
    assert [r.number for r in services.front_desk.day(hotel.rita).under_maintenance] == ["101"]


def test_front_desk_needs_staff(services, hotel):
    from hotel.domain.actor import Actor

    with pytest.raises(PermissionDeniedError):
        services.front_desk.day(Actor(None, label="anonymous"))

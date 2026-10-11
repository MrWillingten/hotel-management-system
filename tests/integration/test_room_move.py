"""Moving guests to another room (story 6.5)."""

from datetime import date, timedelta

import pytest

from hotel.domain.billing import LineKind
from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    InvalidStateTransitionError,
    PermissionDeniedError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest
from hotel.domain.rooms import Housekeeping

TODAY = date(2026, 7, 8)  # the test clock's day


def _book(services, hotel, room="204", arrival=TODAY, nights=4, adults=2, guest=None):
    return services.reservations.create(
        hotel.boss,
        guest_id=(guest or hotel.amira).id,
        period=StayPeriod(arrival, arrival + timedelta(days=nights)),
        rooms=[RoomRequest(hotel.rooms[room].id, adults)],
    )


def _move(services, hotel, reservation, to="205", frm="204", actor=None, **extra):
    current = services.reservations.get(hotel.boss, reservation.id)
    return services.reservations.move_room(
        actor or hotel.rita,
        reservation.id,
        version=current.version,
        from_room_id=hotel.rooms[frm].id,
        to_room_id=hotel.rooms[to].id,
        **extra,
    )


def _actions(services):
    with services.uow_factory() as uow:
        return [entry.action for entry in uow.audit.iterate()]


@pytest.fixture
def in_house(services, hotel, clock):
    """Amira in 204 from today for 4 nights, checked in; two nights later."""
    reservation = _book(services, hotel)
    services.reservations.check_in(hotel.rita, reservation.id, version=reservation.version)
    clock.advance(timedelta(days=2))
    return reservation


def test_mid_stay_move_keeps_the_nights_spent_and_the_prices(services, hotel, in_house):
    moved = _move(services, hotel, in_house)
    old, new = moved.rooms
    assert old.number == "204"
    assert old.moved_out_on == TODAY + timedelta(days=2)
    assert new.number == "205"
    assert new.is_current
    assert [r.number for r in moved.current_rooms] == ["205"]
    assert [n.night for n in moved.nights_of(hotel.rooms["204"].id)] == [
        TODAY,
        TODAY + timedelta(days=1),
    ]
    assert len(moved.nights_of(hotel.rooms["205"].id)) == 2
    assert moved.accommodation_total == Money.from_dinars(4 * 180)  # courtesy: same price
    nights = [
        line
        for line in services.billing.bill(hotel.boss, moved.id).lines
        if line.kind is LineKind.NIGHTS
    ]
    assert [(line.label, line.quantity) for line in nights] == [("204", 2), ("205", 2)]
    assert "reservation.room_moved" in _actions(services)


def test_the_old_room_is_freed_and_must_be_cleaned(services, hotel, in_house):
    _move(services, hotel, in_house)
    rooms = {o.room.number: o for o in services.rooms.list_rooms(hotel.boss)}
    assert rooms["204"].room.housekeeping is Housekeeping.DIRTY
    assert rooms["204"].status.value == "AVAILABLE"
    assert rooms["205"].status.value == "OCCUPIED"
    # Someone else can book 204 tonight.
    _book(
        services, hotel, room="204", arrival=TODAY + timedelta(days=2), nights=1, guest=hotel.karim
    )


def test_check_out_after_a_move_dirties_only_the_current_room(services, hotel, in_house):
    _move(services, hotel, in_house)
    services.rooms.set_housekeeping(hotel.rita, hotel.rooms["204"].id, Housekeeping.CLEAN)
    current = services.reservations.get(hotel.boss, in_house.id)
    services.invoices.check_out(hotel.rita, in_house.id, version=current.version)
    rooms = {o.room.number: o.room for o in services.rooms.list_rooms(hotel.boss)}
    assert rooms["204"].housekeeping is Housekeeping.CLEAN
    assert rooms["205"].housekeeping is Housekeeping.DIRTY


def test_a_manager_may_charge_the_new_rooms_price(services, hotel, in_house):
    with pytest.raises(PermissionDeniedError):
        _move(services, hotel, in_house, to="401", charge_new_rate=True)
    moved = _move(services, hotel, in_house, to="401", actor=hotel.boss, charge_new_rate=True)
    assert moved.accommodation_total == Money.from_dinars(2 * 180 + 2 * 320)


def test_a_confirmed_stay_moves_completely(services, hotel):
    reservation = _book(services, hotel, arrival=TODAY + timedelta(days=5))
    moved = _move(services, hotel, reservation)
    assert [r.number for r in moved.rooms] == ["205"]  # never slept in 204: no trace
    rooms = {o.room.number: o.room for o in services.rooms.list_rooms(hotel.boss)}
    assert rooms["204"].housekeeping is Housekeeping.INSPECTED  # nobody used it


def test_the_new_room_must_be_free_big_enough_and_in_service(services, hotel, in_house):
    _book(
        services, hotel, room="205", arrival=TODAY + timedelta(days=3), nights=1, guest=hotel.karim
    )
    with pytest.raises(ConflictError, match="room_unavailable"):
        _move(services, hotel, in_house)
    small = services.rooms.create_room(
        hotel.boss,
        number="102",
        category_id=hotel.rooms["101"].category_id,
        capacity=1,
        nightly_rate=Money.from_dinars(90),
    )
    hotel.rooms["102"] = small
    with pytest.raises(BusinessRuleViolation, match="capacity_exceeded"):
        _move(services, hotel, in_house, to="102")
    # The failed attempts changed nothing.
    assert [r.number for r in services.reservations.get(hotel.boss, in_house.id).rooms] == ["204"]


def test_move_refusals(services, hotel, in_house, clock):
    with pytest.raises(ValidationError, match="move_unknown_room"):
        _move(services, hotel, in_house, frm="101")
    with pytest.raises(BusinessRuleViolation, match="move_room_already_used"):
        _move(services, hotel, in_house, to="204")
    moved = _move(services, hotel, in_house)
    with pytest.raises(BusinessRuleViolation, match="move_room_already_used"):
        _move(services, hotel, moved, frm="205", to="204")  # back to the room they left
    with pytest.raises(StaleDataError):
        services.reservations.move_room(
            hotel.rita,
            in_house.id,
            version=1,
            from_room_id=hotel.rooms["205"].id,
            to_room_id=hotel.rooms["101"].id,
        )
    clock.advance(timedelta(days=2))  # departure day: no night left
    with pytest.raises(BusinessRuleViolation, match="move_nothing_left"):
        _move(services, hotel, moved, frm="205", to="101")


def test_finished_stays_cannot_move(services, hotel):
    reservation = _book(services, hotel, arrival=TODAY + timedelta(days=5))
    services.reservations.cancel(hotel.boss, reservation.id, version=reservation.version)
    with pytest.raises(InvalidStateTransitionError):
        _move(services, hotel, reservation)


def test_the_stay_can_still_be_extended_after_a_move(services, hotel, in_house):
    moved = _move(services, hotel, in_house)
    longer = StayPeriod(moved.period.arrival, moved.period.departure + timedelta(days=1))
    current = services.reservations.get(hotel.boss, moved.id)
    changed = services.reservations.modify(
        hotel.rita,
        moved.id,
        version=current.version,
        period=longer,
        rooms=[RoomRequest(hotel.rooms["205"].id, 2)],
    )
    assert len(changed.nights_of(hotel.rooms["204"].id)) == 2  # history untouched
    assert len(changed.nights_of(hotel.rooms["205"].id)) == 3
    assert changed.rooms[0].moved_out_on == TODAY + timedelta(days=2)
    # The old room cannot come back through a change.
    with pytest.raises(BusinessRuleViolation, match="checked_in_limits"):
        services.reservations.modify(
            hotel.rita,
            moved.id,
            version=changed.version,
            period=longer,
            rooms=[RoomRequest(hotel.rooms["204"].id, 2), RoomRequest(hotel.rooms["205"].id, 2)],
        )


def test_candidates_are_free_big_enough_and_closest_first(services, hotel, in_house):
    rooms = services.reservations.move_candidates(hotel.rita, in_house.id, hotel.rooms["204"].id)
    assert [r.number for r in rooms] == ["205", "101", "401"]  # same category, then price
    assert services.reservations.move_candidates(hotel.rita, in_house.id, 999) == []

from datetime import date, timedelta

import pytest

from hotel.domain.errors import ConflictError
from hotel.domain.money import Money
from hotel.domain.reservations import RoomRequest
from tests.integration.test_booking import book, stay
from tests.integration.test_change_and_cancel import _check_in

TODAY = date(2026, 7, 8)


def _update(services, hotel, number, **changes):
    room = services.rooms.get_room(hotel.boss, hotel.rooms[number].id).room
    fields = {
        "number": room.number,
        "category_id": room.category_id,
        "capacity": room.capacity,
        "nightly_rate": room.nightly_rate,
        "in_service": room.in_service,
        **changes,
    }
    return services.rooms.update_room(hotel.boss, room.id, version=room.version, **fields)


def test_calendar(services, hotel):
    r = book(services, hotel, stay(9, 11), "204")
    occupied = _check_in(services, book(services, hotel, stay(8, 9), "205", guest=hotel.karim))
    services.rooms.schedule_maintenance(
        hotel.boss,
        hotel.rooms["101"].id,
        first_night=date(2026, 7, 10),
        reopens_on=date(2026, 7, 12),
        reason="Paint",
    )
    _update(services, hotel, "401", in_service=False)
    calendar = services.reservations.calendar(hotel.rita, TODAY - timedelta(days=1), days=5)
    assert calendar.days[0] == date(2026, 7, 7)
    rows = {row.room.number: [c.kind for c in row.cells] for row in calendar.rows}
    assert rows["204"] == ["PAST", "FREE", "RESERVED", "RESERVED", "FREE"]
    assert rows["205"] == ["PAST", "OCCUPIED", "FREE", "FREE", "FREE"]
    assert rows["101"] == ["PAST", "FREE", "FREE", "MAINTENANCE", "MAINTENANCE"]
    assert rows["401"] == ["OUT_OF_SERVICE"] * 5
    cells_204 = next(row for row in calendar.rows if row.room.number == "204").cells
    assert [c.starts_here for c in cells_204[2:4]] == [True, False]
    assert cells_204[2].code == r.code
    assert cells_204[2].guest_name == "Amira Ben Salah"
    assert occupied.status == "CHECKED_IN"
    assert len(services.reservations.calendar(hotel.rita, TODAY, days=99).days) == 31


def test_room_cannot_go_out_of_service_with_future_bookings(services, hotel):
    r = book(services, hotel, stay(15, 17), "204")
    with pytest.raises(ConflictError, match="has_future_bookings") as caught:
        _update(services, hotel, "204", in_service=False)
    assert caught.value.params["codes"] == r.code
    services.reservations.cancel(hotel.rita, r.id, version=r.version)
    assert not _update(services, hotel, "204", in_service=False).in_service


def test_capacity_cannot_drop_below_a_booking(services, hotel):
    services.reservations.create(
        hotel.rita,
        guest_id=hotel.amira.id,
        period=stay(15, 17),
        rooms=[RoomRequest(hotel.rooms["401"].id, 3, 1)],
    )
    with pytest.raises(ConflictError, match="capacity_conflict"):
        _update(services, hotel, "401", capacity=3)
    assert _update(services, hotel, "401", capacity=5).capacity == 5
    # Other changes stay possible while the booking exists.
    assert _update(services, hotel, "401", nightly_rate=Money.from_dinars(300)).capacity == 5


def test_past_bookings_do_not_block_room_changes(services, hotel, clock):
    book(services, hotel, stay(8, 9), "204")
    clock.advance(timedelta(days=3))
    assert not _update(services, hotel, "204", in_service=False).in_service


def test_maintenance_over_a_booking_is_refused(services, hotel):
    book(services, hotel, stay(12, 14), "204")
    with pytest.raises(ConflictError, match=r"maintenance\.conflict"):
        services.rooms.schedule_maintenance(
            hotel.boss,
            hotel.rooms["204"].id,
            first_night=date(2026, 7, 13),
            reopens_on=date(2026, 7, 16),
            reason="Paint",
        )

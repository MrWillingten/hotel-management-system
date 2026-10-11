import threading
from datetime import date, timedelta

import pytest

from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.paging import PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import ReservationStatus, RoomRequest
from hotel.persistence.repositories.reservations import ReservationFilter
from hotel.services.reservations import RoomUnavailableError

TODAY = date(2026, 7, 8)


def stay(first_day: int, last_day: int) -> StayPeriod:
    """July first_day to July last_day."""
    return StayPeriod(date(2026, 7, first_day), date(2026, 7, last_day))


def book(services, hotel, period, *numbers, guest=None, adults=1, actor=None):
    return services.reservations.create(
        actor or hotel.rita,
        guest_id=(guest or hotel.amira).id,
        period=period,
        rooms=[RoomRequest(hotel.rooms[n].id, adults) for n in numbers],
    )


def test_create_locks_prices_per_night(services, hotel):
    r = book(services, hotel, stay(10, 13), "204", "101", adults=2)
    assert r.code == "R-2026-00001"
    assert r.status is ReservationStatus.CONFIRMED
    assert len(r.nights) == 6
    assert r.accommodation_total == Money.from_dinars(3 * 180 + 3 * 120)
    assert {room.number for room in r.rooms} == {"204", "101"}
    assert r.guest_name == "Amira Ben Salah"
    # A later price change never touches existing bookings (locked per night).
    room = hotel.rooms["204"]
    services.rooms.update_room(
        hotel.boss,
        room.id,
        version=room.version,
        number="204",
        category_id=room.category_id,
        capacity=2,
        nightly_rate=Money.from_dinars(250),
        in_service=True,
    )
    assert services.reservations.get(hotel.rita, r.id).accommodation_total == Money(900_000)


def test_codes_are_sequential(services, hotel):
    codes = [book(services, hotel, stay(10 + i, 11 + i), "204").code for i in range(3)]
    assert codes == ["R-2026-00001", "R-2026-00002", "R-2026-00003"]


def test_scenario_4_3_conflict_is_refused_with_alternatives(services, hotel):
    """§4.3: room booked 12-14 July; a guest asks for 10-15 July."""
    book(services, hotel, stay(12, 14), "204", guest=hotel.karim)
    with pytest.raises(RoomUnavailableError) as caught:
        book(services, hotel, stay(10, 15), "204")
    error = caught.value
    assert error.params == {"room": "204", "first": "2026-07-12", "last": "2026-07-13", "count": 2}
    # Same category first, then the closest price; the requested room is not suggested.
    assert [r.number for r in error.alternatives] == ["205", "101", "401"]


def test_same_day_turnover_is_allowed(services, hotel):
    book(services, hotel, stay(10, 12), "204", guest=hotel.karim)
    r = book(services, hotel, stay(12, 14), "204")  # arrives the day Karim leaves
    assert r.period.arrival == date(2026, 7, 12)


def test_capacity_rule(services, hotel):
    with pytest.raises(BusinessRuleViolation, match="capacity_exceeded"):
        book(services, hotel, stay(10, 12), "204", adults=3)
    r = services.reservations.create(
        hotel.rita,
        guest_id=hotel.amira.id,
        period=stay(10, 12),
        rooms=[RoomRequest(hotel.rooms["401"].id, 2, 2)],
    )
    assert r.occupants == 4


def test_maintenance_blocks_bookings(services, hotel):
    services.rooms.schedule_maintenance(
        hotel.boss,
        hotel.rooms["204"].id,
        first_night=date(2026, 7, 11),
        reopens_on=date(2026, 7, 13),
        reason="Paint",
    )
    with pytest.raises(RoomUnavailableError):
        book(services, hotel, stay(10, 12), "204")
    book(services, hotel, stay(13, 15), "204")


def test_out_of_service_and_unknown_rooms(services, hotel):
    room = hotel.rooms["101"]
    services.rooms.update_room(
        hotel.boss,
        room.id,
        version=room.version,
        number="101",
        category_id=room.category_id,
        capacity=2,
        nightly_rate=room.nightly_rate,
        in_service=False,
    )
    with pytest.raises(ConflictError, match="room_out_of_service"):
        book(services, hotel, stay(10, 12), "101")
    with pytest.raises(NotFoundError):
        services.reservations.create(
            hotel.rita, guest_id=hotel.amira.id, period=stay(10, 12), rooms=[RoomRequest(999, 1)]
        )


def test_guest_checks(services, hotel):
    flagged = services.guests.set_flags(
        hotel.boss,
        hotel.karim.id,
        version=hotel.karim.version,
        is_vip=False,
        do_not_rent=True,
        reason="Unpaid",
    )
    with pytest.raises(BusinessRuleViolation, match="do_not_rent"):
        book(services, hotel, stay(10, 12), "204", guest=flagged)
    with pytest.raises(NotFoundError):
        services.reservations.create(
            hotel.rita,
            guest_id=999,
            period=stay(10, 12),
            rooms=[RoomRequest(hotel.rooms["204"].id, 1)],
        )


def test_dates_and_notes_are_validated(services, hotel):
    with pytest.raises(ValidationError, match="arrival_in_past"):
        book(services, hotel, stay(7, 9), "204")
    with pytest.raises(ValidationError, match="notes"):
        services.reservations.create(
            hotel.rita,
            guest_id=hotel.amira.id,
            period=stay(10, 12),
            rooms=[RoomRequest(hotel.rooms["204"].id, 1)],
            notes="x" * 501,
        )


def test_quote_matches_the_booking(services, hotel):
    requests = [RoomRequest(hotel.rooms["401"].id, 3, 1), RoomRequest(hotel.rooms["101"].id, 1)]
    quote = services.reservations.quote(
        hotel.rita, guest_id=hotel.amira.id, period=stay(10, 14), rooms=requests
    )
    assert quote.total == Money.from_dinars(4 * 320 + 4 * 120)
    assert [line.subtotal for line in quote.lines] == [
        Money.from_dinars(1280),
        Money.from_dinars(480),
    ]
    booked = services.reservations.create(
        hotel.rita, guest_id=hotel.amira.id, period=stay(10, 14), rooms=requests
    )
    assert booked.accommodation_total == quote.total


def test_a_failed_booking_leaves_no_trace_and_no_gap(services, hotel):
    book(services, hotel, stay(10, 12), "204")
    with pytest.raises(RoomUnavailableError):
        services.reservations.create(
            hotel.rita,
            guest_id=hotel.karim.id,
            period=stay(10, 12),
            rooms=[RoomRequest(hotel.rooms["205"].id, 1), RoomRequest(hotel.rooms["204"].id, 1)],
        )
    assert book(services, hotel, stay(10, 12), "205").code == "R-2026-00002"  # no gap


def test_availability_search(services, hotel):
    book(services, hotel, stay(10, 12), "204")
    free = services.reservations.find_available_rooms(hotel.rita, stay(11, 13))
    assert [r.number for r in free] == ["101", "205", "401"]
    four = services.reservations.find_available_rooms(hotel.rita, stay(11, 13), min_capacity=3)
    assert [r.number for r in four] == ["401"]
    deluxe = services.reservations.find_available_rooms(
        hotel.rita, stay(12, 13), category_id=hotel.rooms["204"].category_id
    )
    assert [r.number for r in deluxe] == ["204", "205"]  # 204 is free again on the 12th


def test_two_receptionists_book_the_same_room_at_the_same_time(services, hotel):
    """C1: exactly one of two simultaneous bookings for the same room succeeds."""
    barrier = threading.Barrier(2)
    outcomes = []

    def attempt(guest):
        barrier.wait()  # start both bookings at the same instant
        try:
            book(services, hotel, stay(20, 25), "204", guest=guest)
            outcomes.append("booked")
        except RoomUnavailableError:
            outcomes.append("refused")

    threads = [threading.Thread(target=attempt, args=(g,)) for g in (hotel.amira, hotel.karim)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == ["booked", "refused"]
    with services.uow_factory() as uow:
        nights = uow.reservations.blocked_nights(stay(20, 25))
    assert len(nights[hotel.rooms["204"].id]) == 5


def test_history_and_search(services, hotel):
    first = book(services, hotel, stay(10, 12), "204")
    book(services, hotel, stay(15, 17), "205")
    book(services, hotel, stay(20, 22), "101", guest=hotel.karim)
    history = services.reservations.for_guest(hotel.rita, hotel.amira.id)
    assert [r.period.arrival.day for r in history] == [15, 10]
    page = services.reservations.search(
        hotel.rita, ReservationFilter(query="haddad"), PageRequest()
    )
    assert [r.guest_name for r in page.items] == ["Karim Haddad"]
    by_code = services.reservations.search(
        hotel.rita, ReservationFilter(query="r-2026-00001"), PageRequest()
    )
    assert [r.id for r in by_code.items] == [first.id]
    arriving = services.reservations.search(
        hotel.rita,
        ReservationFilter(
            arriving_from=date(2026, 7, 12),
            arriving_until=date(2026, 7, 16),
            status=ReservationStatus.CONFIRMED,
        ),
        PageRequest(),
    )
    assert [r.period.arrival.day for r in arriving.items] == [15]
    with pytest.raises(NotFoundError):
        services.reservations.get(hotel.rita, 999)


def test_creation_is_audited(services, hotel):
    r = book(services, hotel, stay(10, 13), "204")
    with services.uow_factory() as uow:
        entry = list(uow.audit.iterate())[-1]
    assert (entry.action, entry.entity_id, entry.username) == (
        "reservation.created",
        str(r.id),
        "rita",
    )
    assert entry.details["total"] == "540.000"


def test_room_status_tonight(services, hotel, clock):
    book(services, hotel, StayPeriod(TODAY, TODAY + timedelta(days=2)), "204")
    statuses = {o.room.number: o.status for o in services.rooms.list_rooms(hotel.rita)}
    assert statuses["204"] == "RESERVED"
    assert statuses["205"] == "AVAILABLE"


def test_form_tokens_work_once_for_their_owner(services, hotel, clock):
    token = services.form_tokens.issue(hotel.rita)
    assert not services.form_tokens.consume(hotel.boss, token)  # someone else's token
    assert services.form_tokens.consume(hotel.rita, token)
    assert not services.form_tokens.consume(hotel.rita, token)  # second click
    old = services.form_tokens.issue(hotel.rita)
    clock.advance(timedelta(hours=9))
    assert not services.form_tokens.consume(hotel.rita, old)  # expired
    assert not services.form_tokens.consume(hotel.rita, None)


def test_the_database_guard_becomes_a_clean_conflict(services, hotel):
    """Defence in depth: even with the Python check bypassed, no double booking and no crash."""
    from hotel.domain.reservations import Reservation, RoomNight

    book(services, hotel, stay(10, 12), "204")
    clash = Reservation(
        None,
        "R-TEST",
        hotel.karim.id,
        stay(11, 13),
        nights=[RoomNight(hotel.rooms["204"].id, date(2026, 7, 11), Money(1))],
        created_at=services.clock.now(),
    )
    with pytest.raises(ConflictError, match="night_taken"), services.uow_factory() as uow:
        uow.reservations.add(clash)

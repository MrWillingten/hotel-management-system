from datetime import date, timedelta

import pytest

from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from hotel.domain.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.rooms import RoomStatus
from hotel.domain.users import User

TODAY = date(2026, 7, 8)  # the fixed test clock


@pytest.fixture
def boss(manager):
    return Actor(manager)


@pytest.fixture
def deluxe(services, boss):
    return services.rooms.create_category(boss, name="Deluxe", description="Sea view")


@pytest.fixture
def room_204(services, boss, deluxe):
    return services.rooms.create_room(
        boss, number="204", category_id=deluxe.id, capacity=2, nightly_rate=Money.from_dinars(180)
    )


def _actions(services):
    with services.uow_factory() as uow:
        return [e.action for e in uow.audit.iterate()]


def test_categories(services, boss, deluxe):
    with pytest.raises(ConflictError):
        services.rooms.create_category(boss, name="deluxe")  # case-insensitive
    suite = services.rooms.create_category(boss, name="Suite")
    with pytest.raises(ConflictError):
        services.rooms.update_category(
            boss, suite.id, version=suite.version, name="Deluxe", description=""
        )
    renamed = services.rooms.update_category(
        boss, suite.id, version=suite.version, name="Royal suite", description="Top floor"
    )
    with pytest.raises(StaleDataError):
        services.rooms.update_category(boss, suite.id, version=1, name="X", description="")
    with pytest.raises(NotFoundError):
        services.rooms.update_category(boss, 99, version=1, name="X", description="")
    names = [c.name for c in services.rooms.list_categories(boss)]
    assert names == ["Deluxe", "Royal suite"]
    assert renamed.version == 2


def test_create_room(services, boss, room_204):
    assert room_204.number == "204"
    assert room_204.category_name == "Deluxe"
    assert room_204.nightly_rate == Money(180_000)
    assert _actions(services)[-1] == "room.created"


def test_room_numbers_are_unique(services, boss, deluxe, room_204):
    with pytest.raises(ConflictError) as caught:
        services.rooms.create_room(
            boss, number=" 204 ", category_id=deluxe.id, capacity=2, nightly_rate=Money(1)
        )
    assert caught.value.fields == {"number": "room.number_taken"}


def test_room_needs_an_existing_category(services, boss):
    with pytest.raises(ValidationError, match="category_unknown"):
        services.rooms.create_room(
            boss, number="1", category_id=42, capacity=1, nightly_rate=Money(1)
        )


def test_update_room_and_take_it_out_of_service(services, boss, deluxe, room_204):
    updated = services.rooms.update_room(
        boss,
        room_204.id,
        version=room_204.version,
        number="204A",
        category_id=deluxe.id,
        capacity=3,
        nightly_rate=Money.from_dinars(200),
        in_service=False,
        notes="Renovated",
    )
    assert (updated.number, updated.capacity, updated.in_service) == ("204A", 3, False)
    assert services.rooms.get_room(boss, room_204.id).status is RoomStatus.OUT_OF_SERVICE
    with services.uow_factory() as uow:
        entry = list(uow.audit.iterate())[-1]
    assert entry.details["fields"] == ["number", "capacity", "nightly_rate", "in_service", "notes"]
    with pytest.raises(StaleDataError):
        services.rooms.update_room(
            boss,
            room_204.id,
            version=room_204.version,
            number="204",
            category_id=deluxe.id,
            capacity=2,
            nightly_rate=Money(1),
            in_service=True,
        )


def test_receptionists_can_look_but_not_change(services, room_204, deluxe):
    rita = Actor(User(9, "rita", "Rita", "x", Role.RECEPTIONIST))
    assert [o.room.number for o in services.rooms.list_rooms(rita)] == ["204"]
    with pytest.raises(PermissionDeniedError):
        services.rooms.create_room(
            rita, number="1", category_id=deluxe.id, capacity=1, nightly_rate=Money(1)
        )
    with pytest.raises(PermissionDeniedError):
        services.rooms.schedule_maintenance(
            rita, room_204.id, first_night=TODAY, reopens_on=TODAY + timedelta(days=1), reason="x"
        )


def test_scenario_4_1_maintenance_blocks_the_period(services, boss, room_204):
    """§4.1: room 204 (deluxe, 180 DT) closed for maintenance for three days."""
    m = services.rooms.schedule_maintenance(
        boss,
        room_204.id,
        first_night=TODAY,
        reopens_on=TODAY + timedelta(days=3),
        reason="Bathroom repair",
    )
    assert m.last_night == date(2026, 7, 10)
    with services.uow_factory() as uow:
        blocked = uow.maintenance.blocked_nights(room_204.id, m.period)
    assert blocked == [date(2026, 7, 8), date(2026, 7, 9), date(2026, 7, 10)]
    assert services.rooms.get_room(boss, room_204.id).status is RoomStatus.MAINTENANCE


def test_overlapping_maintenance_is_refused(services, boss, room_204):
    services.rooms.schedule_maintenance(
        boss,
        room_204.id,
        first_night=TODAY + timedelta(days=2),
        reopens_on=TODAY + timedelta(days=5),
        reason="Paint",
    )
    with pytest.raises(ConflictError) as caught:
        services.rooms.schedule_maintenance(
            boss,
            room_204.id,
            first_night=TODAY,
            reopens_on=TODAY + timedelta(days=4),
            reason="Plumbing",
        )
    assert caught.value.params == {"first": "2026-07-10", "last": "2026-07-11", "count": 2}
    # Back-to-back periods are fine: the reopening day is not a closed night.
    services.rooms.schedule_maintenance(
        boss,
        room_204.id,
        first_night=TODAY,
        reopens_on=TODAY + timedelta(days=2),
        reason="Plumbing",
    )


def test_the_database_itself_refuses_a_double_block(services, room_204):
    """Even if the service check were skipped, room_night's primary key refuses it."""
    import sqlite3

    from hotel.domain.period import StayPeriod
    from hotel.domain.rooms import MaintenancePeriod

    period = StayPeriod(TODAY, TODAY + timedelta(days=2))
    with services.uow_factory() as uow:
        uow.maintenance.add(
            MaintenancePeriod(None, room_204.id, period, "A", created_at=services.clock.now())
        )
    with pytest.raises(sqlite3.IntegrityError), services.uow_factory() as uow:
        uow.maintenance.add(
            MaintenancePeriod(None, room_204.id, period, "B", created_at=services.clock.now())
        )


@pytest.mark.parametrize(
    ("first", "reopens", "code"),
    [
        (TODAY, TODAY, "reopen_not_after_start"),
        (TODAY - timedelta(days=1), TODAY + timedelta(days=1), "in_past"),
        (TODAY, TODAY + timedelta(days=91), "too_long"),
    ],
)
def test_maintenance_validation(services, boss, room_204, first, reopens, code):
    with pytest.raises(ValidationError, match=code):
        services.rooms.schedule_maintenance(
            boss, room_204.id, first_night=first, reopens_on=reopens, reason="x"
        )


def test_cancel_future_maintenance(services, boss, room_204):
    m = services.rooms.schedule_maintenance(
        boss,
        room_204.id,
        first_night=TODAY + timedelta(days=5),
        reopens_on=TODAY + timedelta(days=7),
        reason="Paint",
    )
    assert services.rooms.cancel_maintenance(boss, m.id) is None
    assert services.rooms.maintenance_for_room(boss, room_204.id) == []


def test_end_ongoing_maintenance_early(services, boss, clock, room_204):
    m = services.rooms.schedule_maintenance(
        boss, room_204.id, first_night=TODAY, reopens_on=TODAY + timedelta(days=5), reason="Paint"
    )
    clock.advance(timedelta(days=2))
    ended = services.rooms.cancel_maintenance(boss, m.id)
    assert ended.reopens_on == date(2026, 7, 10)
    assert services.rooms.get_room(boss, room_204.id).status is RoomStatus.AVAILABLE
    clock.advance(timedelta(days=1))
    with pytest.raises(ValidationError, match="already_over"):
        services.rooms.cancel_maintenance(boss, m.id)
    with pytest.raises(NotFoundError):
        services.rooms.cancel_maintenance(boss, 999)


def test_missing_room(services, boss):
    with pytest.raises(NotFoundError):
        services.rooms.get_room(boss, 1)
    with pytest.raises(NotFoundError):
        services.rooms.maintenance_for_room(boss, 1)

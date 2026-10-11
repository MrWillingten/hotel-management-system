"""The night audit (story 5.4)."""

from datetime import date, timedelta

import pytest

from hotel.domain.actor import Actor
from hotel.domain.errors import PermissionDeniedError, ValidationError
from hotel.domain.money import Money
from hotel.domain.night_audit import days_to_close
from hotel.domain.reservations import ReservationStatus
from tests.integration.test_booking import book, stay


def test_closing_a_day(services, hotel, clock):
    never = book(services, hotel, stay(8, 10), "204")  # never arrives
    staying = book(services, hotel, stay(8, 9), "205", guest=hotel.karim)
    services.reservations.check_in(hotel.rita, staying.id, version=staying.version)
    clock.advance(timedelta(days=1))  # 9 July: close the 8th
    outcome = services.night_audit.run(hotel.boss)
    assert outcome.day == date(2026, 7, 8)
    assert not outcome.already_closed
    assert outcome.no_shows == [never.code]
    assert outcome.overdue == []  # 205 leaves today, not overdue yet
    assert services.reservations.get(hotel.boss, never.id).status is ReservationStatus.NO_SHOW
    snapshot = outcome.snapshot
    assert (snapshot.nights_sold, snapshot.nights_sellable) == (1, 4)  # no-show night released
    assert snapshot.room_value == Money.from_dinars(180)
    assert snapshot.no_shows == 1


def test_running_twice_changes_nothing(services, hotel, clock):
    book(services, hotel, stay(8, 10), "204")
    clock.advance(timedelta(days=1))
    first = services.night_audit.run(hotel.boss)
    book(services, hotel, stay(9, 10), "101")  # the hotel keeps working
    second = services.night_audit.run(hotel.boss, date(2026, 7, 8))
    assert second.already_closed
    assert second.snapshot == first.snapshot
    with services.uow_factory() as uow:
        assert [e.action for e in uow.audit.iterate()].count("night_audit.closed") == 1


def test_overdue_departures_are_flagged_not_changed(services, hotel, clock):
    r = book(services, hotel, stay(8, 9), "204")
    services.reservations.check_in(hotel.rita, r.id, version=r.version)
    clock.advance(timedelta(days=2))  # 10 July, the guest never checked out
    outcome = services.night_audit.run(hotel.boss)
    assert outcome.overdue == [r.code]
    assert services.reservations.get(hotel.boss, r.id).status is ReservationStatus.CHECKED_IN


def test_only_finished_days_and_only_managers(services, hotel):
    with pytest.raises(ValidationError, match="day_not_over"):
        services.night_audit.run(hotel.boss, date(2026, 7, 8))
    with pytest.raises(PermissionDeniedError):
        services.night_audit.run(hotel.rita)


def test_catch_up_closes_every_missed_day(services, hotel, clock):
    system = Actor.system("night-audit")
    clock.advance(timedelta(days=1))
    assert [o.day for o in services.night_audit.catch_up(system)] == [date(2026, 7, 8)]
    clock.advance(timedelta(days=3))  # the application was stopped for three days
    assert [o.day.day for o in services.night_audit.catch_up(system)] == [9, 10, 11]
    assert services.night_audit.catch_up(system) == []
    assert len(services.night_audit.recent(hotel.boss)) == 4


def test_days_to_close():
    today = date(2026, 7, 20)
    assert days_to_close(None, today) == [date(2026, 7, 19)]
    assert days_to_close(date(2026, 7, 19), today) == []
    assert days_to_close(date(2026, 7, 17), today) == [date(2026, 7, 18), date(2026, 7, 19)]
    assert len(days_to_close(date(2025, 1, 1), today)) == 31  # at most a month

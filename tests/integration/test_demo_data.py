import pytest

from hotel.demo import is_demo, seed_demo
from hotel.domain.actor import Actor
from hotel.domain.errors import BusinessRuleViolation
from hotel.domain.paging import PageRequest


def test_demo_data_fills_an_empty_hotel(services):
    assert not is_demo(services)
    result = seed_demo(services, guests=30, history_days=10)
    assert result.rooms == 17
    assert result.guests == 30
    assert result.reservations >= 15
    assert result.invoices >= 5  # a replayed week: check-outs and a no-show
    assert set(result.accounts) == {"demo.manager", "demo.reception"}
    assert is_demo(services)
    system = Actor.system()
    rooms = services.rooms.list_rooms(system)
    assert {o.room.number for o in rooms} >= {"101", "204", "403"}
    room_204 = next(o.room for o in rooms if o.room.number == "204")
    assert (room_204.category_name, str(room_204.nightly_rate)) == ("Deluxe", "180.000")
    assert any(o.status == "MAINTENANCE" for o in rooms)
    guests = services.guests.search(system, "", PageRequest(per_page=100))
    assert guests.total == 30
    assert sum(g.is_vip for g in guests.items) >= 3
    assert sum(g.do_not_rent for g in guests.items) == 1
    login = services.auth.login("demo.reception", result.accounts["demo.reception"], ip="1.1.1.1")
    assert not login.user.must_change_password
    day = services.front_desk.day(system)
    assert day.in_house  # guests still in the house today
    assert day.to_clean  # rooms left this morning
    assert services.invoices.search(system, "", PageRequest()).total == result.invoices
    assert services.audit.verify(system).ok  # the replayed history is a valid chain


def test_demo_data_is_deterministic(services, settings, clock, tmp_path):
    from hotel.bootstrap import build_services
    from hotel.config import Settings

    seed_demo(services, guests=10, history_days=5)
    other = build_services(
        Settings(environment="testing", data_dir=tmp_path / "b", scrypt_n=2**10), clock=clock
    )
    seed_demo(other, guests=10, history_days=5)

    def names(svc):
        return [g.full_name for g in svc.guests.search(Actor.system(), "", PageRequest()).items]

    assert names(services) == names(other)


def test_demo_data_refuses_a_hotel_in_use(services, manager):
    seed_demo(services, guests=2)
    with pytest.raises(BusinessRuleViolation, match="not_empty"):
        seed_demo(services)


def test_existing_demo_accounts_are_kept(services):
    first = seed_demo(services, guests=1)
    assert first.accounts

"""Delete or archive (story 6.17): never-used records are deleted, used ones archived."""

from datetime import timedelta

import pytest

from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from hotel.domain.guests import GuestDetails
from hotel.domain.money import Money
from hotel.domain.paging import PageRequest
from hotel.domain.removal import RemovalAction
from hotel.domain.taxes import PercentTax, TaxExemption
from tests.conftest import MANAGER_PASSWORD
from tests.integration.test_booking import book, stay


def _actions(services):
    with services.uow_factory() as uow:
        return [e.action for e in uow.audit.iterate()]


def _guest_names(services, hotel, **kwargs):
    page = services.guests.search(hotel.boss, "", PageRequest(per_page=100), **kwargs)
    return {g.full_name for g in page.items}


# ------------------------------------------------------------ guests
def test_a_guest_who_never_booked_is_deleted(services, hotel):
    lina = services.guests.register(hotel.boss, GuestDetails("Lina", "Trabelsi", "CIN", "07654321"))
    assert services.guests.removal_plan(hotel.boss, lina.id).action is RemovalAction.DELETE
    with pytest.raises(PermissionDeniedError):
        services.guests.remove(hotel.rita, lina.id)
    assert services.guests.remove(hotel.boss, lina.id) is RemovalAction.DELETE
    with pytest.raises(NotFoundError):
        services.guests.get(hotel.boss, lina.id)
    assert "guest.deleted" in _actions(services)


def test_a_guest_with_stays_is_archived_then_restored(services, hotel, clock):
    r = book(services, hotel, stay(8, 9), "204")  # Amira
    plan = services.guests.removal_plan(hotel.boss, hotel.amira.id)
    assert not plan.allowed  # a stay to come: not now
    with pytest.raises(BusinessRuleViolation, match="has_current_stays"):
        services.guests.remove(hotel.boss, hotel.amira.id)
    services.reservations.cancel(hotel.boss, r.id, version=r.version)
    plan = services.guests.removal_plan(hotel.boss, hotel.amira.id)
    assert plan.action is RemovalAction.ARCHIVE
    assert plan.uses == 1
    assert services.guests.remove(hotel.boss, hotel.amira.id) is RemovalAction.ARCHIVE
    # Hidden from the list and from bookings, still readable with its history.
    assert "Amira Ben Salah" not in _guest_names(services, hotel)
    assert "Amira Ben Salah" in _guest_names(services, hotel, archived=True)
    assert services.guests.get(hotel.boss, hotel.amira.id).is_archived
    assert services.guests.count_archived(hotel.boss) == 1
    with pytest.raises(BusinessRuleViolation, match=r"guest\.archived"):
        book(services, hotel, stay(20, 21), "205")
    services.guests.restore(hotel.boss, hotel.amira.id)
    assert "Amira Ben Salah" in _guest_names(services, hotel)
    assert {"guest.archived", "guest.restored"} <= set(_actions(services))


# ------------------------------------------------------------ rooms
def test_a_room_never_used_is_deleted(services, hotel):
    room = services.rooms.create_room(
        hotel.boss,
        number="999",
        category_id=hotel.rooms["101"].category_id,
        capacity=2,
        nightly_rate=Money.from_dinars(100),
    )
    assert services.rooms.remove(hotel.boss, room.id) is RemovalAction.DELETE
    assert "999" not in {o.room.number for o in services.rooms.list_rooms(hotel.boss)}


def test_a_room_with_future_bookings_cannot_go_then_is_archived(services, hotel, clock):
    book(services, hotel, stay(10, 12), "204")
    with pytest.raises(ConflictError, match="has_future_bookings"):
        services.rooms.remove(hotel.boss, hotel.rooms["204"].id)
    clock.advance(timedelta(days=10))  # the stay is over
    assert services.rooms.remove(hotel.boss, hotel.rooms["204"].id) is RemovalAction.ARCHIVE
    numbers = {o.room.number for o in services.rooms.list_rooms(hotel.rita)}
    assert "204" not in numbers
    archived = services.rooms.list_rooms(hotel.rita, archived=True)
    assert [o.room.number for o in archived] == ["204"]
    assert not archived[0].room.in_service  # archived rooms cannot be booked
    room = archived[0].room
    with pytest.raises(BusinessRuleViolation, match=r"room\.archived"):
        services.rooms.update_room(
            hotel.boss,
            room.id,
            version=room.version,
            number="204",
            category_id=room.category_id,
            capacity=2,
            nightly_rate=room.nightly_rate,
            in_service=True,
        )
    restored = services.rooms.restore(hotel.boss, hotel.rooms["204"].id)
    assert not restored.is_archived
    assert not restored.in_service  # still out of service until a manager decides


# ------------------------------------------------------------ extra services
def test_extra_services_are_deleted_or_archived(services, hotel, clock):
    unused = services.extras.create(hotel.boss, name="Spa", unit_price=Money.from_dinars(50))
    used = services.extras.create(hotel.boss, name="Breakfast", unit_price=Money.from_dinars(15))
    r = book(services, hotel, stay(8, 10), "204")
    r = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    services.extras.charge(
        hotel.rita, r.id, extra_id=used.id, quantity=1, charge_date=r.period.arrival
    )
    assert services.extras.remove(hotel.boss, unused.id) is RemovalAction.DELETE
    assert services.extras.remove(hotel.boss, used.id) is RemovalAction.ARCHIVE
    assert services.extras.catalogue(hotel.rita) == []
    assert [e.name for e in services.extras.catalogue(hotel.boss, archived=True)] == ["Breakfast"]
    # The charge on the stay keeps its description and price.
    assert [c.description for c in services.extras.charges_for(hotel.rita, r.id)] == ["Breakfast"]
    with pytest.raises(BusinessRuleViolation, match=r"extra\.archived"):
        services.extras.update(
            hotel.boss, used.id, version=2, name="Breakfast", unit_price=Money(1), is_active=True
        )
    services.extras.restore(hotel.boss, used.id)
    assert [e.name for e in services.extras.catalogue(hotel.boss)] == ["Breakfast"]
    assert services.extras.catalogue(hotel.boss, active_only=True) == []  # still inactive


# ------------------------------------------------------------ tax rules
def test_tax_rules_are_deleted_or_archived(services, hotel):
    vat = services.hotel_settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    levy = services.hotel_settings.create_tax_rule(hotel.boss, PercentTax(name="Levy", rate_bp=100))
    r = book(services, hotel, stay(8, 10), "204")
    services.billing.exempt_from_tax(
        hotel.boss, TaxExemption(id=None, reservation_id=r.id, tax_rule_id=levy.id, reason="x")
    )
    assert services.hotel_settings.remove_tax_rule(hotel.boss, vat.id) is RemovalAction.DELETE
    assert services.hotel_settings.remove_tax_rule(hotel.boss, levy.id) is RemovalAction.ARCHIVE
    assert services.hotel_settings.tax_rules(hotel.boss) == []
    assert [t.name for t in services.hotel_settings.tax_rules(hotel.boss, archived=True)] == [
        "Levy"
    ]
    bill = services.billing.bill(hotel.rita, r.id)
    assert bill.tax.is_zero()  # neither rule applies any more
    services.hotel_settings.restore_tax_rule(hotel.boss, levy.id)
    assert services.hotel_settings.count_archived_taxes(hotel.boss) == 0
    with pytest.raises(NotFoundError):
        services.hotel_settings.remove_tax_rule(hotel.boss, vat.id)


# ------------------------------------------------------------ staff
def test_staff_accounts_are_deleted_or_archived(services, hotel):
    newcomer = services.users.create_user(
        hotel.boss,
        username="sami",
        full_name="Sami",
        role=Role.RECEPTIONIST,
        temporary_password=MANAGER_PASSWORD,
    )
    # Never signed in, never did anything: deleted.
    assert services.users.remove(hotel.boss, newcomer.id) is RemovalAction.DELETE
    # Rita booked a stay (the audit log remembers her): archived, signed out.
    book(services, hotel, stay(8, 9), "204")
    session = services.auth.login("rita", MANAGER_PASSWORD, ip="10.0.0.1").token
    assert services.users.remove(hotel.boss, hotel.rita.user.id) is RemovalAction.ARCHIVE
    assert services.auth.authenticate_session(session) is None
    rita = services.users.get_user(hotel.boss, hotel.rita.user.id)
    assert rita.is_archived
    assert not rita.is_active
    assert "rita" not in {u.username for u in services.users.list_users(hotel.boss)}
    with pytest.raises(BusinessRuleViolation, match=r"user\.archived"):
        services.users.set_active(hotel.boss, rita.id, version=rita.version, active=True)
    services.users.restore(hotel.boss, rita.id)
    assert "rita" in {u.username for u in services.users.list_users(hotel.boss)}


def test_nobody_removes_themselves_or_the_last_manager(services, hotel):
    with pytest.raises(BusinessRuleViolation, match="cannot_remove_self"):
        services.users.remove(hotel.boss, hotel.boss.user.id)
    # From the command line (system actor), the only manager is still protected.
    with pytest.raises(BusinessRuleViolation, match="last_manager"):
        services.users.remove(Actor.system(), hotel.boss.user.id)
    # With a second active manager, one manager may archive the other.
    other = services.users.create_user(
        hotel.boss,
        username="sami",
        full_name="Sami",
        role=Role.MANAGER,
        temporary_password=MANAGER_PASSWORD,
    )
    assert services.users.remove(Actor(other), hotel.boss.user.id) is RemovalAction.ARCHIVE

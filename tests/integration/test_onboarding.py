"""The walk-through state and the self-ticking checklist (story 6.14)."""

from datetime import date

import pytest

from hotel.domain.actor import Actor
from hotel.domain.errors import PermissionDeniedError
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest


def test_a_new_account_sees_the_welcome_and_an_empty_checklist(services, hotel):
    state = services.onboarding.state(hotel.rita)
    assert state.show_welcome
    assert state.show_checklist
    assert state.progress == (0, 5)  # receptionists: front-desk items only
    assert services.onboarding.state(hotel.boss).progress[1] == 9


def test_items_tick_themselves_from_the_audit_log(services, hotel):
    services.reservations.create(
        hotel.rita,
        guest_id=hotel.amira.id,
        period=StayPeriod(date(2026, 7, 10), date(2026, 7, 12)),
        rooms=[RoomRequest(hotel.rooms["204"].id, 1)],
    )
    done = {item.key for item, ticked in services.onboarding.state(hotel.rita).items if ticked}
    assert done == {"book"}
    # The manager registered the guests in the fixture: that counts for them, not for Rita.
    boss = {item.key for item, ticked in services.onboarding.state(hotel.boss).items if ticked}
    assert {"register_guest", "add_room", "add_staff"} <= boss
    assert "book" not in boss


def test_finishing_dismissing_and_restarting(services, hotel):
    services.onboarding.finish_tour(hotel.rita)
    services.onboarding.finish_tour(hotel.rita)  # twice is fine
    assert not services.onboarding.state(hotel.rita).show_welcome
    services.onboarding.dismiss_checklist(hotel.rita)
    assert not services.onboarding.state(hotel.rita).show_checklist
    assert services.onboarding.state(hotel.boss).show_welcome  # per person
    services.onboarding.restart(hotel.rita)
    state = services.onboarding.state(hotel.rita)
    assert state.show_welcome
    assert state.show_checklist


def test_onboarding_needs_a_person(services):
    with pytest.raises(PermissionDeniedError):
        services.onboarding.state(Actor.system())

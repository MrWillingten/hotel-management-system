"""Personal API tokens (story 6.3)."""

from datetime import timedelta

import pytest

from hotel.domain.actor import Actor
from hotel.domain.errors import (
    BusinessRuleViolation,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from hotel.services.auth import hash_token
from tests.conftest import MANAGER_PASSWORD


def _actions(services):
    with services.uow_factory() as uow:
        return [entry.action for entry in uow.audit.iterate()]


def test_a_token_is_shown_once_and_stored_hashed(services, hotel):
    created = services.api_tokens.create(hotel.boss, name="  Occupancy   board ", days=90)
    assert created.secret.startswith("hotel_")
    assert len(created.secret) > 40
    assert created.token.name == "Occupancy board"
    assert created.token.prefix == created.secret[:10]
    assert created.token.expires_at == services.clock.now() + timedelta(days=90)
    with services.uow_factory() as uow:
        stored = uow.api_tokens.get(created.token.id)
    assert stored.token_hash == hash_token(created.secret)
    assert created.secret not in repr(stored)
    assert services.api_tokens.authenticate(created.secret).id == hotel.boss.user.id
    assert "api_token.created" in _actions(services)


def test_only_managers_hold_tokens(services, hotel):
    with pytest.raises(PermissionDeniedError):
        services.api_tokens.create(hotel.rita, name="x", days=30)
    with pytest.raises(PermissionDeniedError):
        services.api_tokens.list_own(hotel.rita)


@pytest.mark.parametrize(("name", "days"), [("", 30), ("x" * 61, 30), ("ok", 7), ("ok", 0)])
def test_name_and_lifetime_are_validated(services, hotel, name, days):
    with pytest.raises(ValidationError):
        services.api_tokens.create(hotel.boss, name=name, days=days)


def test_at_most_ten_active_tokens(services, hotel):
    for i in range(10):
        services.api_tokens.create(hotel.boss, name=f"t{i}", days=30)
    with pytest.raises(BusinessRuleViolation, match="too_many"):
        services.api_tokens.create(hotel.boss, name="eleventh", days=30)


def test_tokens_stop_working_when_revoked_expired_or_the_owner_changes(services, hotel, clock):
    revoked = services.api_tokens.create(hotel.boss, name="a", days=30)
    services.api_tokens.revoke(hotel.boss, revoked.token.id)
    services.api_tokens.revoke(hotel.boss, revoked.token.id)  # twice: no error, one audit entry
    assert services.api_tokens.authenticate(revoked.secret) is None
    assert _actions(services).count("api_token.revoked") == 1

    expiring = services.api_tokens.create(hotel.boss, name="b", days=30)
    clock.advance(timedelta(days=30))
    assert services.api_tokens.authenticate(expiring.secret) is None

    # A second manager whose token dies when they stop being a manager.
    other = services.users.create_user(
        hotel.boss,
        username="sami",
        full_name="Sami",
        role="MANAGER",
        temporary_password=MANAGER_PASSWORD,
    )
    token = services.api_tokens.create(Actor(other), name="c", days=30)
    assert services.api_tokens.authenticate(token.secret).id == other.id
    services.users.update_user(
        hotel.boss, other.id, version=other.version, full_name="Sami", role="RECEPTIONIST"
    )
    assert services.api_tokens.authenticate(token.secret) is None


def test_managers_cannot_revoke_someone_elses_token(services, hotel):
    other = services.users.create_user(
        hotel.boss,
        username="sami",
        full_name="Sami",
        role="MANAGER",
        temporary_password=MANAGER_PASSWORD,
    )
    token = services.api_tokens.create(Actor(other), name="c", days=30)
    with pytest.raises(NotFoundError):
        services.api_tokens.revoke(hotel.boss, token.token.id)
    with pytest.raises(NotFoundError):
        services.api_tokens.revoke(hotel.boss, 999)


@pytest.mark.parametrize("secret", [None, "", "hotel_unknown", "x" * 200])
def test_unknown_tokens_are_refused(services, hotel, secret):
    assert services.api_tokens.authenticate(secret) is None


def test_last_use_is_recorded_at_most_once_a_minute(services, hotel, clock):
    created = services.api_tokens.create(hotel.boss, name="a", days=30)
    services.api_tokens.authenticate(created.secret)
    first = services.api_tokens.list_own(hotel.boss)[0].last_used_at
    clock.advance(timedelta(seconds=30))
    services.api_tokens.authenticate(created.secret)
    assert services.api_tokens.list_own(hotel.boss)[0].last_used_at == first
    clock.advance(timedelta(seconds=31))
    services.api_tokens.authenticate(created.secret)
    assert services.api_tokens.list_own(hotel.boss)[0].last_used_at == clock.now()

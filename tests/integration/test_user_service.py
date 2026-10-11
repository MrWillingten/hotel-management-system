import pytest

from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from hotel.domain.errors import (
    AuthenticationError,
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    StaleDataError,
    ValidationError,
)
from tests.conftest import MANAGER_PASSWORD

TEMP = "temporary-pass-4521"


@pytest.fixture
def boss(manager):
    return Actor(manager, ip="10.0.0.1")


@pytest.fixture
def rita(services, boss):
    return services.users.create_user(
        boss,
        username="Rita",
        full_name="  Rita   Trabelsi ",
        role=Role.RECEPTIONIST,
        temporary_password=TEMP,
    )


def _actions(services):
    with services.uow_factory() as uow:
        return [e.action for e in uow.audit.iterate()]


def test_create_user(services, rita):
    assert rita.username == "rita"
    assert rita.full_name == "Rita Trabelsi"
    assert rita.must_change_password
    assert _actions(services)[-1] == "user.created"


def test_username_must_be_unique(services, boss, rita):
    with pytest.raises(ConflictError) as caught:
        services.users.create_user(
            boss,
            username="RITA",
            full_name="Other",
            role=Role.RECEPTIONIST,
            temporary_password=TEMP,
        )
    assert caught.value.fields == {"username": "user.username_taken"}


def test_temporary_password_follows_the_policy(services, boss):
    with pytest.raises(ValidationError):
        services.users.create_user(
            boss,
            username="sami",
            full_name="Sami",
            role=Role.RECEPTIONIST,
            temporary_password="short",
        )


def test_receptionists_cannot_manage_staff(services, rita):
    receptionist = Actor(rita)
    with pytest.raises(PermissionDeniedError):
        services.users.list_users(receptionist)
    with pytest.raises(PermissionDeniedError):
        services.users.create_user(
            receptionist, username="x2x", full_name="X", role=Role.MANAGER, temporary_password=TEMP
        )


def test_update_user_with_optimistic_locking(services, boss, rita):
    updated = services.users.update_user(
        boss, rita.id, version=rita.version, full_name="Rita B.", role=Role.MANAGER
    )
    assert updated.role is Role.MANAGER
    with pytest.raises(StaleDataError):
        services.users.update_user(
            boss, rita.id, version=rita.version, full_name="Stale", role=Role.RECEPTIONIST
        )
    with pytest.raises(NotFoundError):
        services.users.get_user(boss, 999)


def test_last_manager_cannot_be_demoted_or_deactivated(services, boss, manager):
    with pytest.raises(BusinessRuleViolation, match="last_manager"):
        services.users.update_user(
            boss,
            manager.id,
            version=manager.version,
            full_name=manager.full_name,
            role=Role.RECEPTIONIST,
        )
    other = services.users.create_user(
        boss, username="omar", full_name="Omar", role=Role.MANAGER, temporary_password=TEMP
    )
    services.users.set_active(boss, other.id, version=other.version, active=False)
    with pytest.raises(BusinessRuleViolation, match="last_manager"):
        services.users.set_active(Actor.system(), manager.id, version=manager.version, active=False)


def test_managers_cannot_deactivate_themselves(services, boss, manager):
    with pytest.raises(BusinessRuleViolation, match="cannot_deactivate_self"):
        services.users.set_active(boss, manager.id, version=manager.version, active=False)


def test_deactivation_ends_sessions_immediately(services, boss, rita):
    token = services.auth.login("rita", TEMP, ip="10.0.0.2").token
    assert services.auth.authenticate_session(token) is not None
    rita = services.users.get_user(boss, rita.id)  # signing in changed the record
    rita = services.users.set_active(boss, rita.id, version=rita.version, active=False)
    assert services.auth.authenticate_session(token) is None
    with pytest.raises(AuthenticationError):
        services.auth.login("rita", TEMP, ip="10.0.0.2")
    rita = services.users.set_active(boss, rita.id, version=rita.version, active=True)
    assert services.users.set_active(boss, rita.id, version=rita.version, active=True) == rita
    assert "user.deactivated" in _actions(services)


def test_reset_password_unlocks_and_signs_out(services, boss, rita):
    token = services.auth.login("rita", TEMP, ip="10.0.0.2").token
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            services.auth.login("rita", "wrong password!!", ip="10.0.0.3")
    services.users.reset_password(boss, rita.id, temporary_password="another-temp-9988")
    assert services.auth.authenticate_session(token) is None
    user = services.auth.login("rita", "another-temp-9988", ip="10.0.0.2").user
    assert user.must_change_password
    assert not user.is_locked(services.clock.now())


def test_unlock(services, boss, rita):
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            services.auth.login("rita", "wrong password!!", ip="10.0.0.3")
    services.users.unlock(boss, rita.id)
    assert services.auth.login("rita", TEMP, ip="10.0.0.3").user.id == rita.id


def test_change_own_password(services, rita):
    first = services.auth.login("rita", TEMP, ip="10.0.0.2").token
    second = services.auth.login("rita", TEMP, ip="10.0.0.3").token
    me = Actor(services.auth.authenticate_session(first))
    with pytest.raises(ValidationError, match="current_wrong"):
        services.users.change_own_password(me, current_password="nope", new_password="x" * 20)
    with pytest.raises(ValidationError, match="same_as_current"):
        services.users.change_own_password(me, current_password=TEMP, new_password=TEMP)
    with pytest.raises(ValidationError, match="contains_username"):
        services.users.change_own_password(me, current_password=TEMP, new_password="rita-the-best!")
    user = services.users.change_own_password(
        me, current_password=TEMP, new_password="jasmine tea at noon", current_token=first
    )
    assert not user.must_change_password
    assert services.auth.authenticate_session(first) is not None  # this session stays
    assert services.auth.authenticate_session(second) is None  # the others end


def test_change_password_without_a_token_ends_every_session(services, manager):
    token = services.auth.login("mona", MANAGER_PASSWORD, ip="10.0.0.2").token
    services.users.change_own_password(
        Actor(manager), current_password=MANAGER_PASSWORD, new_password="a brand new passphrase"
    )
    assert services.auth.authenticate_session(token) is None


def test_system_actor_has_no_own_password(services, manager):
    with pytest.raises(PermissionDeniedError):
        services.users.change_own_password(Actor.system(), current_password="a", new_password="b")

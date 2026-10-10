from datetime import timedelta

import pytest

from hotel.domain.enums import Role
from hotel.domain.errors import AuthenticationError, BusinessRuleViolation, ValidationError
from hotel.services.auth import hash_token
from hotel.services.passwords import PasswordHasher, ScryptParams

PASSWORD = "cognac-and-cedar-2026"


@pytest.fixture
def manager(services):
    return services.auth.create_first_manager(" Mona ", "Mona Ben Salah", PASSWORD)


def _login(services, password=PASSWORD, username="mona", ip="10.0.0.1"):
    return services.auth.login(username, password, ip=ip, user_agent="pytest")


def _fail(services, times, **kwargs):
    for _ in range(times):
        with pytest.raises(AuthenticationError):
            _login(services, password="wrong password!!", **kwargs)


# ------------------------------------------------------------ first manager
def test_first_manager_is_created_once(services, manager):
    assert manager.username == "mona"
    assert manager.role is Role.MANAGER
    assert services.auth.has_users()
    with pytest.raises(BusinessRuleViolation):
        services.auth.create_first_manager("other", "Other", PASSWORD)


def test_first_manager_input_is_validated(services):
    with pytest.raises(ValidationError, match="username"):
        services.auth.create_first_manager("x", "Mona", PASSWORD)
    with pytest.raises(ValidationError, match="full_name"):
        services.auth.create_first_manager("mona", "   ", PASSWORD)
    with pytest.raises(ValidationError, match=r"password\.too_short"):
        services.auth.create_first_manager("mona", "Mona", "short")
    assert not services.auth.has_users()


def test_password_check_uses_the_bundled_common_list(services):
    with pytest.raises(ValidationError, match="too_common"):
        services.auth.check_password("123456789012", username="mona")


# ------------------------------------------------------------ login
def test_successful_login_opens_a_session(services, manager):
    result = _login(services, username="MONA")  # usernames are case-insensitive
    assert result.user.id == manager.id
    assert len(result.token) >= 40
    assert services.auth.authenticate_session(result.token).id == manager.id
    with services.uow_factory() as uow:
        # Only the hash of the token is stored.
        assert uow.sessions.get(hash_token(result.token)) is not None
        assert uow.sessions.get(result.token) is None


def test_unknown_user_and_wrong_password_give_the_same_error(services, manager):
    with pytest.raises(AuthenticationError) as unknown:
        _login(services, username="nobody")
    with pytest.raises(AuthenticationError) as wrong:
        _login(services, password="not the password")
    assert unknown.value.code == wrong.value.code == "auth.invalid_credentials"


def test_unknown_user_still_spends_time_hashing(services, monkeypatch):
    calls = []
    monkeypatch.setattr(services.auth._hasher, "verify_dummy", calls.append)
    with pytest.raises(AuthenticationError):
        _login(services, username="nobody")
    assert calls == [PASSWORD]


def test_failures_are_recorded_even_though_login_raises(services, manager):
    """The error is raised after the transaction commits, so counters are kept."""
    _fail(services, 2)
    with services.uow_factory() as uow:
        assert uow.users.get(manager.id).failed_attempts == 2
        assert (
            uow.login_failures.count_for_ip_since(
                "10.0.0.1", services.clock.now() - timedelta(hours=1)
            )
            == 2
        )


def test_account_locks_after_five_failures_even_with_the_right_password(services, clock, manager):
    _fail(services, 5)
    with pytest.raises(AuthenticationError):
        _login(services)  # correct password, but locked
    clock.advance(timedelta(minutes=15))
    assert _login(services).user.id == manager.id


def test_attempts_while_locked_do_not_extend_the_lock(services, clock, manager):
    _fail(services, 5)
    clock.advance(timedelta(minutes=10))
    _fail(services, 3)
    clock.advance(timedelta(minutes=5))
    assert _login(services).user.id == manager.id


def test_successful_login_resets_failures(services, manager):
    _fail(services, 3)
    _login(services)
    with services.uow_factory() as uow:
        assert uow.users.get(manager.id).failed_attempts == 0


def test_one_address_is_throttled_across_accounts(services, manager):
    for i in range(20):
        with pytest.raises(AuthenticationError):
            _login(services, username=f"guess{i}")
    with pytest.raises(AuthenticationError) as caught:
        _login(services)
    assert caught.value.code == "auth.too_many_attempts"
    assert _login(services, ip="10.0.0.2").user.id == manager.id  # other computers unaffected


def test_inactive_account_cannot_sign_in(services, manager):
    with services.uow_factory() as uow:
        user = uow.users.get(manager.id)
        user.is_active = False
        uow.users.update(user)
    with pytest.raises(AuthenticationError):
        _login(services)


def test_password_hash_is_upgraded_when_the_cost_changes(services, manager):
    assert manager.password_hash.startswith("scrypt$1024$")
    # Simulate a later version of the program that uses a stronger cost setting.
    services.auth._hasher = PasswordHasher(ScryptParams(n=2**11))
    _login(services)
    with services.uow_factory() as uow:
        assert uow.users.get(manager.id).password_hash.startswith("scrypt$2048$")


# ------------------------------------------------------------ sessions
def test_session_expires_after_idle_time(services, clock, manager):
    token = _login(services).token
    clock.advance(timedelta(minutes=29))
    assert services.auth.authenticate_session(token) is not None
    clock.advance(timedelta(minutes=29))  # activity above refreshed "last seen"
    assert services.auth.authenticate_session(token) is not None
    clock.advance(timedelta(minutes=30))
    assert services.auth.authenticate_session(token) is None
    with services.uow_factory() as uow:
        assert uow.sessions.count_for_user(manager.id) == 0  # removed, not just ignored


def test_session_has_an_absolute_lifetime(services, clock, manager):
    token = _login(services).token
    for _ in range(25):  # active every 29 minutes for more than 12 hours
        clock.advance(timedelta(minutes=29))
        services.auth.authenticate_session(token)
    assert services.auth.authenticate_session(token) is None


def test_deactivating_a_user_ends_their_session_immediately(services, manager):
    token = _login(services).token
    with services.uow_factory() as uow:
        user = uow.users.get(manager.id)
        user.is_active = False
        uow.users.update(user)
    assert services.auth.authenticate_session(token) is None


def test_logout_destroys_the_server_session(services, manager):
    token = _login(services).token
    services.auth.logout(token)
    assert services.auth.authenticate_session(token) is None


@pytest.mark.parametrize("token", [None, "", "x" * 500, "not-a-real-token"])
def test_garbage_tokens_are_rejected(services, token):
    assert services.auth.authenticate_session(token) is None
    services.auth.logout(token)  # must not raise


def test_old_sessions_are_cleaned_up_at_next_login(services, clock, manager):
    _login(services)
    clock.advance(timedelta(hours=13))
    _login(services)
    with services.uow_factory() as uow:
        assert uow.sessions.count_for_user(manager.id) == 1

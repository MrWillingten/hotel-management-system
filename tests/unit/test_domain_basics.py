from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from hotel.domain.clock import FixedClock, SystemClock
from hotel.domain.enums import Role
from hotel.domain.errors import (
    HotelError,
    PermissionDeniedError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.passwords import PasswordPolicy
from hotel.domain.users import (
    LockoutPolicy,
    User,
    UserSession,
    normalize_username,
    validate_username,
)
from hotel.services.authorization import require_role

TUNIS = ZoneInfo("Africa/Tunis")
NOON = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------ errors
def test_errors_carry_codes_and_params_not_sentences():
    error = ValidationError("password.too_short", fields={"password": "x"}, min_length=12)
    assert error.code == "password.too_short"
    assert error.params == {"min_length": 12}
    assert error.fields == {"password": "x"}
    assert StaleDataError().code == "stale_data"
    assert isinstance(StaleDataError(), HotelError)
    assert str(HotelError()) == "error"


# ------------------------------------------------------------ clock
def test_fixed_clock_uses_the_hotel_time_zone_for_today():
    late_evening_utc = datetime(2026, 7, 8, 23, 30, tzinfo=UTC)  # 00:30 on the 9th in Tunis
    clock = FixedClock(late_evening_utc, TUNIS)
    assert clock.today() == date(2026, 7, 9)
    clock.advance(timedelta(hours=1))
    assert clock.now() == late_evening_utc + timedelta(hours=1)


def test_fixed_clock_refuses_naive_datetimes():
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 7, 8), TUNIS)  # noqa: DTZ001


def test_system_clock_is_aware_and_utc():
    now = SystemClock(TUNIS).now()
    assert now.tzinfo is UTC


# ------------------------------------------------------------ usernames
def test_usernames_are_normalised():
    assert normalize_username("  Mona.B ") == "mona.b"
    assert validate_username("Amira_92") == "amira_92"


@pytest.mark.parametrize("bad", ["ab", "a" * 33, "with space", "émile", "x;drop"])
def test_invalid_usernames(bad):
    with pytest.raises(ValidationError):
        validate_username(bad)


# ------------------------------------------------------------ lockout
def _user(**overrides):
    fields = {
        "id": 1,
        "username": "mona",
        "full_name": "Mona",
        "password_hash": "h",
        "role": Role.MANAGER,
    }
    return User(**(fields | overrides))


def test_lock_after_five_failures_then_doubling():
    policy = LockoutPolicy()
    user = _user()
    for _ in range(4):
        user.register_failed_login(NOON, policy)
    assert not user.is_locked(NOON)
    user.register_failed_login(NOON, policy)
    assert user.locked_until == NOON + timedelta(minutes=15)
    assert user.is_locked(NOON + timedelta(minutes=14))
    assert not user.is_locked(NOON + timedelta(minutes=15))
    for _ in range(5):
        user.register_failed_login(NOON, policy)
    assert user.locked_until == NOON + timedelta(minutes=30)


def test_lock_duration_is_capped():
    assert LockoutPolicy().lock_duration(20) == timedelta(hours=24)


def test_successful_login_resets_the_counter():
    user = _user(failed_attempts=7, locked_until=NOON)
    user.register_successful_login()
    assert user.failed_attempts == 0
    assert user.locked_until is None


def test_session_validity():
    session = UserSession("a" * 64, 1, NOON, NOON, NOON + timedelta(hours=12))
    idle = timedelta(minutes=30)
    assert session.is_valid(NOON + timedelta(minutes=29), idle)
    assert not session.is_valid(NOON + timedelta(minutes=30), idle)
    session.last_seen_at = NOON + timedelta(hours=11, minutes=50)
    assert not session.is_valid(NOON + timedelta(hours=12), idle)


# ------------------------------------------------------------ password policy
@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("short", "password.too_short"),
        ("x" * 129, "password.too_long"),
        ("abababababab", "password.too_repetitive"),
        ("mona-is-the-best", "password.contains_username"),
        ("Qwertyuiop123", "password.too_common"),
    ],
)
def test_password_policy_rejections(password, code):
    policy = PasswordPolicy(common_passwords=frozenset({"qwertyuiop123"}))
    with pytest.raises(ValidationError) as caught:
        policy.check(password, username="mona")
    assert caught.value.code == code
    assert caught.value.fields == {"password": code}


def test_password_policy_accepts_a_long_passphrase():
    PasswordPolicy().check("cognac and cedar wood", username="mona")


# ------------------------------------------------------------ authorization
def test_require_role():
    manager = _user()
    receptionist = _user(role=Role.RECEPTIONIST)
    assert require_role(manager, Role.MANAGER) is manager
    with pytest.raises(PermissionDeniedError):
        require_role(receptionist, Role.MANAGER)
    with pytest.raises(PermissionDeniedError):
        require_role(None, Role.MANAGER)
    with pytest.raises(PermissionDeniedError):
        require_role(_user(is_active=False), Role.MANAGER)

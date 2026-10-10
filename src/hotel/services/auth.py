"""Signing in, sessions and the first manager account."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import AuthenticationError, BusinessRuleViolation, ValidationError
from hotel.domain.passwords import PasswordPolicy
from hotel.domain.users import (
    LockoutPolicy,
    User,
    UserSession,
    normalize_username,
    validate_username,
)
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.passwords import PasswordHasher

_MAX_TOKEN_LENGTH = 128
_MAX_USER_AGENT_LENGTH = 200


@dataclass(frozen=True, slots=True)
class AuthSettings:
    lockout: LockoutPolicy = field(default_factory=LockoutPolicy)
    ip_max_failures: int = 20  # failed sign-ins allowed per address...
    ip_window: timedelta = timedelta(minutes=15)  # ...within this window
    session_idle_timeout: timedelta = timedelta(minutes=30)
    session_max_age: timedelta = timedelta(hours=12)
    # Recording "last seen" on every request would mean a database write per
    # page; once a minute is precise enough for a 30-minute idle timeout.
    session_touch_interval: timedelta = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class LoginResult:
    token: str  # goes into the browser cookie, never stored as-is
    user: User


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        hasher: PasswordHasher,
        password_policy: PasswordPolicy,
        settings: AuthSettings | None = None,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._hasher = hasher
        self._password_policy = password_policy
        self._settings = settings or AuthSettings()

    @property
    def session_idle_minutes(self) -> int:
        return int(self._settings.session_idle_timeout.total_seconds() // 60)

    def check_password(self, password: str, *, username: str = "") -> None:
        """Validate a new password against the policy without storing anything."""
        self._password_policy.check(password, username=normalize_username(username))

    # ------------------------------------------------------------ setup
    def has_users(self) -> bool:
        with self._uow() as uow:
            return uow.users.count() > 0

    def create_first_manager(self, username: str, full_name: str, password: str) -> User:
        """Create the very first account. Refused once any account exists."""
        username = validate_username(username)
        full_name = full_name.strip()
        if not 1 <= len(full_name) <= 100:
            raise ValidationError("full_name.invalid", fields={"full_name": "full_name.invalid"})
        self._password_policy.check(password, username=username)
        with self._uow() as uow:
            if uow.users.count() > 0:
                raise BusinessRuleViolation("auth.setup_already_done")
            user = User(
                id=None,
                username=username,
                full_name=full_name,
                password_hash=self._hasher.hash(password),
                role=Role.MANAGER,
                created_at=self._clock.now(),
            )
            return uow.users.add(user)

    # ------------------------------------------------------------ sign in / out
    def login(self, username: str, password: str, *, ip: str, user_agent: str = "") -> LoginResult:
        """Check the credentials and open a new session.

        Every failure raises AuthenticationError with the same code, whether the
        username is unknown, the account is disabled or locked, or the password is
        wrong, so an attacker cannot learn which usernames exist.
        """
        settings = self._settings
        now = self._clock.now()
        lookup_name = normalize_username(username)[:64]
        failure: str | None = None

        with self._uow() as uow:
            uow.login_failures.delete_older_than(now - timedelta(days=1))
            recent = uow.login_failures.count_for_ip_since(ip, now - settings.ip_window)
            if recent >= settings.ip_max_failures:
                failure = "auth.too_many_attempts"
            else:
                user = uow.users.get_by_username(lookup_name) if lookup_name else None
                if user is None or not user.is_active:
                    self._hasher.verify_dummy(password)  # same cost as a real check
                    failure = "auth.invalid_credentials"
                else:
                    # The password is checked even when the account is locked, so a
                    # locked account answers exactly as slowly as an unlocked one.
                    password_ok = self._hasher.verify(password, user.password_hash)
                    locked = user.is_locked(now)
                    if password_ok and not locked:
                        return self._open_session(uow, user, password, ip, user_agent, now)
                    if not locked:  # attempts while locked do not extend the lock
                        user.register_failed_login(now, settings.lockout)
                        uow.users.update(user)
                    failure = "auth.invalid_credentials"
                uow.login_failures.add(ip, lookup_name or None, now)
        # Raised only after the `with` block has committed: raising inside it would
        # roll back the failure counters we have just recorded.
        raise AuthenticationError(failure)

    def _open_session(
        self,
        uow: UnitOfWork,
        user: User,
        password: str,
        ip: str,
        user_agent: str,
        now: datetime,
    ) -> LoginResult:
        settings = self._settings
        user.register_successful_login()
        if self._hasher.needs_rehash(user.password_hash):
            user.password_hash = self._hasher.hash(password)
        uow.users.update(user)
        uow.sessions.delete_stale(
            expired_before=now, idle_since=now - settings.session_idle_timeout
        )
        token = secrets.token_urlsafe(32)  # 256 bits of randomness
        uow.sessions.add(
            UserSession(
                token_hash=hash_token(token),
                user_id=user.id,
                created_at=now,
                last_seen_at=now,
                expires_at=now + settings.session_max_age,
                ip=ip,
                user_agent=user_agent[:_MAX_USER_AGENT_LENGTH] or None,
            )
        )
        return LoginResult(token=token, user=user)

    def authenticate_session(self, token: str | None) -> User | None:
        """Return the signed-in user for a cookie token, or None if it is not valid."""
        if not token or len(token) > _MAX_TOKEN_LENGTH:
            return None
        settings = self._settings
        now = self._clock.now()
        token_hash = hash_token(token)
        with self._uow() as uow:
            session = uow.sessions.get(token_hash)
            if session is None:
                return None
            user = uow.users.get(session.user_id)
            if (
                user is None
                or not user.is_active
                or not session.is_valid(now, settings.session_idle_timeout)
            ):
                uow.sessions.delete(token_hash)
                return None
            if now - session.last_seen_at >= settings.session_touch_interval:
                uow.sessions.touch(token_hash, now)
            return user

    def logout(self, token: str | None) -> None:
        if not token or len(token) > _MAX_TOKEN_LENGTH:
            return
        with self._uow() as uow:
            uow.sessions.delete(hash_token(token))

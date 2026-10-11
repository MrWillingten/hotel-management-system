"""Signing in, sessions and the first manager account."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import AuthenticationError, BusinessRuleViolation
from hotel.domain.passwords import PasswordPolicy
from hotel.domain.totp import hash_recovery_code, looks_like_recovery_code
from hotel.domain.users import (
    LockoutPolicy,
    User,
    UserSession,
    normalize_username,
    validate_full_name,
    validate_username,
)
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
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
    # Time to type the second-factor code after the password, and wrong codes
    # allowed before the password must be typed again.
    challenge_lifetime: timedelta = timedelta(minutes=5)
    challenge_max_attempts: int = 5


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Either a session (`token`) or, when the account has a second factor, a
    `challenge` to present with the code. Both go into the browser and are
    stored only as hashes."""

    user: User
    token: str | None = None
    challenge: str | None = None

    @property
    def needs_code(self) -> bool:
        return self.challenge is not None


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
        full_name = validate_full_name(full_name)
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
            user = uow.users.add(user)
            record(
                uow,
                self._clock,
                Actor.system(),
                "user.created",
                entity="user",
                entity_id=user.id,
                role=user.role.value,
                first_manager=True,
            )
            return user

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
            anonymous = Actor(user=None, ip=ip, label="anonymous")
            if recent >= settings.ip_max_failures:
                failure = "auth.too_many_attempts"
                record(uow, self._clock, anonymous, "auth.throttled")
            else:
                user = uow.users.get_by_username(lookup_name) if lookup_name else None
                if user is None or not user.is_active:
                    self._hasher.verify_dummy(password)  # same cost as a real check
                    failure = "auth.invalid_credentials"
                    # The attempted name is not logged for unknown accounts: people
                    # sometimes type their password into the username field.
                    record(
                        uow,
                        self._clock,
                        anonymous,
                        "auth.login_failed",
                        reason="unknown_or_inactive",
                    )
                else:
                    # The password is checked even when the account is locked, so a
                    # locked account answers exactly as slowly as an unlocked one.
                    password_ok = self._hasher.verify(password, user.password_hash)
                    locked = user.is_locked(now)
                    if password_ok and not locked:
                        if self._hasher.needs_rehash(user.password_hash):
                            user.password_hash = self._hasher.hash(password)
                        if user.two_factor.enabled:
                            return self._challenge(uow, user, ip, now)
                        if user.is_manager:
                            user.two_factor.start_grace(now)
                        return self._open_session(uow, user, ip, user_agent, now)
                    actor = Actor(user=user, ip=ip)
                    if not locked:  # attempts while locked do not extend the lock
                        user.register_failed_login(now, settings.lockout)
                        uow.users.update(user)
                    record(
                        uow,
                        self._clock,
                        actor,
                        "auth.login_failed",
                        entity="user",
                        entity_id=user.id,
                        reason="locked" if locked else "password",
                    )
                    if not locked and user.is_locked(now):
                        record(
                            uow,
                            self._clock,
                            actor,
                            "auth.account_locked",
                            entity="user",
                            entity_id=user.id,
                            until=user.locked_until.isoformat(),
                        )
                    failure = "auth.invalid_credentials"
                uow.login_failures.add(ip, lookup_name or None, now)
        # Raised only after the `with` block has committed: raising inside it would
        # roll back the failure counters we have just recorded.
        raise AuthenticationError(failure)

    def _open_session(
        self,
        uow: UnitOfWork,
        user: User,
        ip: str,
        user_agent: str,
        now: datetime,
        *,
        method: str = "password",
    ) -> LoginResult:
        settings = self._settings
        user.register_successful_login()
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
        record(
            uow,
            self._clock,
            Actor(user=user, ip=ip),
            "auth.login",
            entity="user",
            entity_id=user.id,
            method=method,
        )
        return LoginResult(user=user, token=token)

    # ------------------------------------------------------------ second factor
    def _challenge(self, uow: UnitOfWork, user: User, ip: str, now: datetime) -> LoginResult:
        """The password was right; the session opens only after the code (story 6.1).

        The failure counters are not reset yet: a stolen password alone must
        not wipe the lockout progress of someone guessing codes.
        """
        uow.users.update(user)  # a rehashed password is kept
        uow.login_challenges.delete_expired(now)
        challenge = secrets.token_urlsafe(32)
        uow.login_challenges.add(
            hash_token(challenge), user.id, now + self._settings.challenge_lifetime
        )
        record(
            uow,
            self._clock,
            Actor(user=user, ip=ip),
            "auth.password_accepted",
            entity="user",
            entity_id=user.id,
        )
        return LoginResult(user=user, challenge=challenge)

    def complete_login(
        self, challenge: str | None, code: str, *, ip: str, user_agent: str = ""
    ) -> LoginResult:
        """Second step: a code from the authenticator app or an unused recovery code.

        Wrong codes count like wrong passwords (same account lockout); after
        `challenge_max_attempts` the challenge is gone and the password must be
        typed again. "auth.code_expired" means: start again from the password.
        """
        if not challenge or len(challenge) > _MAX_TOKEN_LENGTH:
            raise AuthenticationError("auth.code_expired")
        settings = self._settings
        now = self._clock.now()
        token_hash = hash_token(challenge)
        code = code[:32]
        failure = "auth.code_expired"
        with self._uow() as uow:
            pending = uow.login_challenges.get(token_hash)
            user = uow.users.get(pending.user_id) if pending else None
            if pending is None or user is None:
                pass
            elif now >= pending.expires_at or not user.is_active or not user.two_factor.enabled:
                uow.login_challenges.delete(token_hash)
            elif user.is_locked(now):
                uow.login_challenges.delete(token_hash)
                failure = "auth.invalid_credentials"
            else:
                method = self._check_code(uow, user, code, now)
                actor = Actor(user=user, ip=ip)
                if method is not None:
                    uow.login_challenges.delete(token_hash)
                    if method == "recovery_code":
                        record(
                            uow,
                            self._clock,
                            actor,
                            "auth.recovery_code_used",
                            entity="user",
                            entity_id=user.id,
                            remaining=uow.recovery_codes.remaining(user.id),
                        )
                    return self._open_session(uow, user, ip, user_agent, now, method=method)
                user.register_failed_login(now, settings.lockout)
                uow.users.update(user)
                record(
                    uow,
                    self._clock,
                    actor,
                    "auth.code_failed",
                    entity="user",
                    entity_id=user.id,
                )
                if pending.attempts + 1 >= settings.challenge_max_attempts or user.is_locked(now):
                    uow.login_challenges.delete(token_hash)
                else:
                    uow.login_challenges.count_attempt(token_hash)
                    failure = "auth.invalid_code"
                uow.login_failures.add(ip, user.username, now)
        raise AuthenticationError(failure)  # after the commit, as in login()

    @staticmethod
    def _check_code(uow: UnitOfWork, user: User, code: str, now: datetime) -> str | None:
        """How the user proved it ("totp" or "recovery_code"), or None."""
        if looks_like_recovery_code(code):
            if uow.recovery_codes.use(user.id, hash_recovery_code(code), now):
                return "recovery_code"
            return None
        if user.two_factor.accept(code, now):
            return "totp"  # the step is saved with the user by _open_session
        return None

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
        token_hash = hash_token(token)
        with self._uow() as uow:
            session = uow.sessions.get(token_hash)
            if session is None:
                return
            uow.sessions.delete(token_hash)
            user = uow.users.get(session.user_id)
            record(
                uow,
                self._clock,
                Actor(user=user),
                "auth.logout",
                entity="user",
                entity_id=session.user_id,
            )

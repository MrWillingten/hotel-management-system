"""Staff accounts and their login sessions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hotel.domain.enums import Role
from hotel.domain.errors import ValidationError

_USERNAME = re.compile(r"^[a-z0-9._-]{3,32}$")


def normalize_username(raw: str) -> str:
    """Canonical form used for storage and lookup: NFKC, trimmed, lower case."""
    return unicodedata.normalize("NFKC", raw).strip().casefold()


def validate_username(raw: str) -> str:
    username = normalize_username(raw)
    if not _USERNAME.fullmatch(username):
        raise ValidationError("username.invalid", fields={"username": "username.invalid"})
    return username


@dataclass(frozen=True, slots=True)
class LockoutPolicy:
    """After every `max_attempts` wrong passwords the account is locked.

    Each new lock lasts twice as long as the previous one (15 min, 30 min,
    1 h...), capped at `max_lock`. A successful login resets everything.
    """

    max_attempts: int = 5
    base_lock: timedelta = timedelta(minutes=15)
    max_lock: timedelta = timedelta(hours=24)

    def lock_duration(self, lock_round: int) -> timedelta:
        return min(self.base_lock * 2 ** (lock_round - 1), self.max_lock)


@dataclass(slots=True)
class User:
    id: int | None
    username: str
    full_name: str
    password_hash: str
    role: Role
    is_active: bool = True
    must_change_password: bool = False
    failed_attempts: int = 0
    locked_until: datetime | None = None
    created_at: datetime | None = None
    version: int = 1  # optimistic locking: incremented on every update

    @property
    def is_manager(self) -> bool:
        return self.role is Role.MANAGER

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until

    def register_failed_login(self, now: datetime, policy: LockoutPolicy) -> None:
        self.failed_attempts += 1
        if self.failed_attempts % policy.max_attempts == 0:
            lock_round = self.failed_attempts // policy.max_attempts
            self.locked_until = now + policy.lock_duration(lock_round)

    def register_successful_login(self) -> None:
        self.failed_attempts = 0
        self.locked_until = None


@dataclass(slots=True)
class UserSession:
    """A server-side login session.

    The browser cookie holds a random token; the database stores only its
    SHA-256 hash, so a stolen database copy cannot be used to hijack sessions.
    """

    token_hash: str
    user_id: int
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip: str | None = None
    user_agent: str | None = field(default=None, repr=False)

    def is_valid(self, now: datetime, idle_timeout: timedelta) -> bool:
        return now < self.expires_at and now - self.last_seen_at < idle_timeout

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from hotel.domain.enums import Role
from hotel.domain.errors import StaleDataError
from hotel.domain.totp import TwoFactor
from hotel.domain.users import User
from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

# Written out in full (not assembled with string formatting) so that every
# query in this file is a constant that can be read and checked as-is.
_SELECT_BY_ID = (
    "SELECT id, username, full_name, password_hash, role, is_active, must_change_password, "
    "failed_attempts, locked_until, created_at, version, totp_secret, "
    "totp_pending_secret, totp_last_step, totp_enabled_at, totp_grace_until, archived_at "
    "FROM app_user WHERE id = ?"
)
_SELECT_ALL = (
    "SELECT id, username, full_name, password_hash, role, is_active, must_change_password, "
    "failed_attempts, locked_until, created_at, version, totp_secret, "
    "totp_pending_secret, totp_last_step, totp_enabled_at, totp_grace_until, archived_at "
    "FROM app_user ORDER BY username"
)
_SELECT_BY_USERNAME = (
    "SELECT id, username, full_name, password_hash, role, is_active, must_change_password, "
    "failed_attempts, locked_until, created_at, version, totp_secret, "
    "totp_pending_secret, totp_last_step, totp_enabled_at, totp_grace_until, archived_at "
    "FROM app_user WHERE username = ?"
)


def _to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        full_name=row["full_name"],
        password_hash=row["password_hash"],
        role=Role(row["role"]),
        is_active=bool(row["is_active"]),
        must_change_password=bool(row["must_change_password"]),
        failed_attempts=row["failed_attempts"],
        locked_until=datetime_from_db(row["locked_until"]),
        created_at=datetime_from_db(row["created_at"]),
        version=row["version"],
        two_factor=TwoFactor(
            secret=row["totp_secret"],
            pending_secret=row["totp_pending_secret"],
            last_step=row["totp_last_step"],
            enabled_at=datetime_from_db(row["totp_enabled_at"]),
            grace_until=datetime_from_db(row["totp_grace_until"]),
        ),
        archived_at=datetime_from_db(row["archived_at"]),
    )


class UserRepository(BaseRepository):
    def get(self, user_id: int) -> User | None:
        row = self._fetch_one(_SELECT_BY_ID, (user_id,))
        return _to_user(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        row = self._fetch_one(_SELECT_BY_USERNAME, (username,))
        return _to_user(row) if row else None

    def list_all(self, *, archived: bool = False) -> list[User]:
        """Accounts in use; archived ones (story 6.17) only when asked for, and then alone."""
        return [
            user
            for user in (_to_user(row) for row in self._fetch_all(_SELECT_ALL))
            if user.is_archived == archived
        ]

    # ------------------------------------------------------------ delete or archive (6.17)
    def count_actions(self, user_id: int) -> int:
        """Entries of the audit log written by this person (every action is audited)."""
        return self._fetch_one("SELECT COUNT(*) FROM audit_log WHERE user_id = ?", (user_id,))[0]

    def count_archived(self) -> int:
        return self._fetch_one("SELECT COUNT(*) FROM app_user WHERE archived_at IS NOT NULL")[0]

    def archive(self, user_id: int, now: datetime | None) -> None:
        """`now` archives (and deactivates), None restores (still deactivated)."""
        if now is None:
            self._execute(
                "UPDATE app_user SET archived_at = NULL, version = version + 1 WHERE id = ?",
                (user_id,),
            )
        else:
            self._execute(
                "UPDATE app_user SET archived_at = ?, is_active = 0, version = version + 1 "
                "WHERE id = ?",
                (datetime_to_db(now), user_id),
            )

    def delete(self, user_id: int) -> bool:
        """Sessions, tokens, recovery codes and onboarding go with it (ON DELETE CASCADE).

        Returns False, changing nothing, if a record still points to the
        account (a foreign key): the caller then archives it instead.
        """
        try:
            self._execute("DELETE FROM app_user WHERE id = ?", (user_id,))
        except sqlite3.IntegrityError:
            return False
        return True

    def count_active_managers(self) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM app_user WHERE role = 'MANAGER' AND is_active = 1"
        )[0]

    def count(self) -> int:
        return self._fetch_one("SELECT COUNT(*) FROM app_user")[0]

    def add(self, user: User) -> User:
        cursor = self._execute(
            "INSERT INTO app_user (username, full_name, password_hash, role, is_active, "
            "must_change_password, failed_attempts, locked_until, created_at, version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                user.username,
                user.full_name,
                user.password_hash,
                user.role.value,
                int(user.is_active),
                int(user.must_change_password),
                user.failed_attempts,
                datetime_to_db(user.locked_until),
                datetime_to_db(user.created_at),
            ),
        )
        user.id = cursor.lastrowid
        user.version = 1
        return user

    def update(self, user: User) -> None:
        """Save changes, refusing if someone else saved this user in the meantime."""
        totp = user.two_factor
        cursor = self._execute(
            "UPDATE app_user SET full_name = ?, password_hash = ?, role = ?, is_active = ?, "
            "must_change_password = ?, failed_attempts = ?, locked_until = ?, "
            "totp_secret = ?, totp_pending_secret = ?, totp_last_step = ?, totp_enabled_at = ?, "
            "totp_grace_until = ?, version = version + 1 "
            "WHERE id = ? AND version = ?",
            (
                user.full_name,
                user.password_hash,
                user.role.value,
                int(user.is_active),
                int(user.must_change_password),
                user.failed_attempts,
                datetime_to_db(user.locked_until),
                totp.secret,
                totp.pending_secret,
                totp.last_step,
                datetime_to_db(totp.enabled_at),
                datetime_to_db(totp.grace_until),
                user.id,
                user.version,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="user", id=user.id)
        user.version += 1


class RecoveryCodeRepository(BaseRepository):
    def replace(self, user_id: int, code_hashes: list[str]) -> None:
        """New codes make every older one, used or not, invalid."""
        self._execute("DELETE FROM recovery_code WHERE user_id = ?", (user_id,))
        for code_hash in code_hashes:
            self._execute(
                "INSERT INTO recovery_code (user_id, code_hash) VALUES (?, ?)", (user_id, code_hash)
            )

    def use(self, user_id: int, code_hash: str, now: datetime) -> bool:
        """Mark an unused code as used; False if it does not exist or was used already."""
        cursor = self._execute(
            "UPDATE recovery_code SET used_at = ? "
            "WHERE user_id = ? AND code_hash = ? AND used_at IS NULL",
            (datetime_to_db(now), user_id, code_hash),
        )
        return cursor.rowcount == 1

    def remaining(self, user_id: int) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM recovery_code WHERE user_id = ? AND used_at IS NULL", (user_id,)
        )[0]

    def delete_for_user(self, user_id: int) -> None:
        self._execute("DELETE FROM recovery_code WHERE user_id = ?", (user_id,))


@dataclass(frozen=True, slots=True)
class LoginChallenge:
    token_hash: str
    user_id: int
    expires_at: datetime
    attempts: int


class LoginChallengeRepository(BaseRepository):
    def add(self, token_hash: str, user_id: int, expires_at: datetime) -> None:
        self._execute(
            "INSERT INTO login_challenge (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, datetime_to_db(expires_at)),
        )

    def get(self, token_hash: str) -> LoginChallenge | None:
        row = self._fetch_one(
            "SELECT token_hash, user_id, expires_at, attempts FROM login_challenge "
            "WHERE token_hash = ?",
            (token_hash,),
        )
        if row is None:
            return None
        return LoginChallenge(
            row["token_hash"], row["user_id"], datetime_from_db(row["expires_at"]), row["attempts"]
        )

    def count_attempt(self, token_hash: str) -> None:
        self._execute(
            "UPDATE login_challenge SET attempts = attempts + 1 WHERE token_hash = ?", (token_hash,)
        )

    def delete(self, token_hash: str) -> None:
        self._execute("DELETE FROM login_challenge WHERE token_hash = ?", (token_hash,))

    def delete_expired(self, now: datetime) -> None:
        self._execute("DELETE FROM login_challenge WHERE expires_at <= ?", (datetime_to_db(now),))

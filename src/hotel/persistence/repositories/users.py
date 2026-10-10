from __future__ import annotations

import sqlite3

from hotel.domain.enums import Role
from hotel.domain.errors import StaleDataError
from hotel.domain.users import User
from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

# Written out in full (not assembled with string formatting) so that every
# query in this file is a constant that can be read and checked as-is.
_SELECT_BY_ID = (
    "SELECT id, username, full_name, password_hash, role, is_active, must_change_password, "
    "failed_attempts, locked_until, created_at, version FROM app_user WHERE id = ?"
)
_SELECT_ALL = (
    "SELECT id, username, full_name, password_hash, role, is_active, must_change_password, "
    "failed_attempts, locked_until, created_at, version FROM app_user ORDER BY username"
)
_SELECT_BY_USERNAME = (
    "SELECT id, username, full_name, password_hash, role, is_active, must_change_password, "
    "failed_attempts, locked_until, created_at, version FROM app_user WHERE username = ?"
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
    )


class UserRepository(BaseRepository):
    def get(self, user_id: int) -> User | None:
        row = self._fetch_one(_SELECT_BY_ID, (user_id,))
        return _to_user(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        row = self._fetch_one(_SELECT_BY_USERNAME, (username,))
        return _to_user(row) if row else None

    def list_all(self) -> list[User]:
        return [_to_user(row) for row in self._fetch_all(_SELECT_ALL)]

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
        cursor = self._execute(
            "UPDATE app_user SET full_name = ?, password_hash = ?, role = ?, is_active = ?, "
            "must_change_password = ?, failed_attempts = ?, locked_until = ?, "
            "version = version + 1 "
            "WHERE id = ? AND version = ?",
            (
                user.full_name,
                user.password_hash,
                user.role.value,
                int(user.is_active),
                int(user.must_change_password),
                user.failed_attempts,
                datetime_to_db(user.locked_until),
                user.id,
                user.version,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="user", id=user.id)
        user.version += 1

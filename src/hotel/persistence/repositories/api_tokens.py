from __future__ import annotations

import sqlite3
from datetime import datetime

from hotel.domain.api_tokens import ApiToken
from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_COLUMNS = (
    "SELECT id, user_id, name, token_hash, prefix, created_at, expires_at, last_used_at, "
    "revoked_at FROM api_token "
)


def _to_token(row: sqlite3.Row) -> ApiToken:
    return ApiToken(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        token_hash=row["token_hash"],
        prefix=row["prefix"],
        created_at=datetime_from_db(row["created_at"]),
        expires_at=datetime_from_db(row["expires_at"]),
        last_used_at=datetime_from_db(row["last_used_at"]),
        revoked_at=datetime_from_db(row["revoked_at"]),
    )


class ApiTokenRepository(BaseRepository):
    def add(self, token: ApiToken) -> ApiToken:
        cursor = self._execute(
            "INSERT INTO api_token (user_id, name, token_hash, prefix, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                token.user_id,
                token.name,
                token.token_hash,
                token.prefix,
                datetime_to_db(token.created_at),
                datetime_to_db(token.expires_at),
            ),
        )
        token.id = cursor.lastrowid
        return token

    def get(self, token_id: int) -> ApiToken | None:
        row = self._fetch_one(_COLUMNS + "WHERE id = ?", (token_id,))
        return _to_token(row) if row else None

    def get_by_hash(self, token_hash: str) -> ApiToken | None:
        row = self._fetch_one(_COLUMNS + "WHERE token_hash = ?", (token_hash,))
        return _to_token(row) if row else None

    def for_user(self, user_id: int) -> list[ApiToken]:
        return [
            _to_token(r)
            for r in self._fetch_all(_COLUMNS + "WHERE user_id = ? ORDER BY id DESC", (user_id,))
        ]

    def count_active(self, user_id: int, now: datetime) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM api_token "
            "WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?",
            (user_id, datetime_to_db(now)),
        )[0]

    def touch(self, token_id: int, now: datetime) -> None:
        self._execute(
            "UPDATE api_token SET last_used_at = ? WHERE id = ?", (datetime_to_db(now), token_id)
        )

    def revoke(self, token_id: int, now: datetime) -> None:
        self._execute(
            "UPDATE api_token SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (datetime_to_db(now), token_id),
        )

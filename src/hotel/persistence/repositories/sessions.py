from __future__ import annotations

from datetime import datetime

from hotel.domain.users import UserSession
from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository


class SessionRepository(BaseRepository):
    def add(self, session: UserSession) -> None:
        self._execute(
            "INSERT INTO user_session (token_hash, user_id, created_at, last_seen_at, "
            "expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session.token_hash,
                session.user_id,
                datetime_to_db(session.created_at),
                datetime_to_db(session.last_seen_at),
                datetime_to_db(session.expires_at),
                session.ip,
                session.user_agent,
            ),
        )

    def get(self, token_hash: str) -> UserSession | None:
        row = self._fetch_one(
            "SELECT token_hash, user_id, created_at, last_seen_at, expires_at, ip, user_agent "
            "FROM user_session WHERE token_hash = ?",
            (token_hash,),
        )
        if row is None:
            return None
        return UserSession(
            token_hash=row["token_hash"],
            user_id=row["user_id"],
            created_at=datetime_from_db(row["created_at"]),
            last_seen_at=datetime_from_db(row["last_seen_at"]),
            expires_at=datetime_from_db(row["expires_at"]),
            ip=row["ip"],
            user_agent=row["user_agent"],
        )

    def touch(self, token_hash: str, now: datetime) -> None:
        self._execute(
            "UPDATE user_session SET last_seen_at = ? WHERE token_hash = ?",
            (datetime_to_db(now), token_hash),
        )

    def delete(self, token_hash: str) -> None:
        self._execute("DELETE FROM user_session WHERE token_hash = ?", (token_hash,))

    def delete_for_user(self, user_id: int) -> int:
        return self._execute("DELETE FROM user_session WHERE user_id = ?", (user_id,)).rowcount

    def delete_stale(self, *, expired_before: datetime, idle_since: datetime) -> int:
        return self._execute(
            "DELETE FROM user_session WHERE expires_at <= ? OR last_seen_at <= ?",
            (datetime_to_db(expired_before), datetime_to_db(idle_since)),
        ).rowcount

    def count_for_user(self, user_id: int) -> int:
        return self._fetch_one("SELECT COUNT(*) FROM user_session WHERE user_id = ?", (user_id,))[0]

from __future__ import annotations

from datetime import datetime

from hotel.persistence.convert import datetime_to_db
from hotel.persistence.repositories.base import BaseRepository


class FormTokenRepository(BaseRepository):
    def add(self, token_hash: str, user_id: int, now: datetime) -> None:
        self._execute(
            "INSERT INTO form_token (token_hash, user_id, created_at) VALUES (?, ?, ?)",
            (token_hash, user_id, datetime_to_db(now)),
        )

    def consume(self, token_hash: str, user_id: int, not_before: datetime) -> bool:
        """Delete the token; True only the first time and only for its owner."""
        row = self._fetch_one(
            "DELETE FROM form_token WHERE token_hash = ? AND user_id = ? AND created_at >= ? "
            "RETURNING token_hash",
            (token_hash, user_id, datetime_to_db(not_before)),
        )
        return row is not None

    def delete_older_than(self, cutoff: datetime) -> None:
        self._execute("DELETE FROM form_token WHERE created_at < ?", (datetime_to_db(cutoff),))

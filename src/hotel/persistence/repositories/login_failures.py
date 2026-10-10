from __future__ import annotations

from datetime import datetime

from hotel.persistence.convert import datetime_to_db
from hotel.persistence.repositories.base import BaseRepository


class LoginFailureRepository(BaseRepository):
    def add(self, ip: str, username: str | None, at: datetime) -> None:
        self._execute(
            "INSERT INTO login_failure (ip, username, at) VALUES (?, ?, ?)",
            (ip, username, datetime_to_db(at)),
        )

    def count_for_ip_since(self, ip: str, since: datetime) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM login_failure WHERE ip = ? AND at > ?",
            (ip, datetime_to_db(since)),
        )[0]

    def delete_older_than(self, cutoff: datetime) -> int:
        return self._execute(
            "DELETE FROM login_failure WHERE at <= ?", (datetime_to_db(cutoff),)
        ).rowcount

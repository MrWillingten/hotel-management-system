from __future__ import annotations

from hotel.persistence.repositories.base import BaseRepository


class SettingRepository(BaseRepository):
    def get(self, key: str) -> str | None:
        row = self._fetch_one("SELECT value FROM setting WHERE key = ?", (key,))
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO setting (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

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

    def with_prefix(self, prefix: str) -> dict[str, str]:
        """Every setting whose key starts with `prefix`, keyed without it."""
        rows = self._fetch_all(
            "SELECT key, value FROM setting WHERE substr(key, 1, ?) = ?", (len(prefix), prefix)
        )
        return {row["key"][len(prefix) :]: row["value"] for row in rows}

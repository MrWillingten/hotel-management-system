from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

Params = Sequence[Any]


def escape_like(text: str) -> str:
    """Make % and _ match themselves in a LIKE pattern (used with ESCAPE '\\').

    Without this, searching for "50%" would match everything starting with "50".
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class BaseRepository:
    """Shared plumbing. Repositories never commit: the UnitOfWork does."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _fetch_one(self, sql: str, params: Params = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, params).fetchone()

    def _fetch_all(self, sql: str, params: Params = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()

    def _execute(self, sql: str, params: Params = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

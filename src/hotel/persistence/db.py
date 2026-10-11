"""Opening and preparing the SQLite database."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from hotel.persistence.migrate import discover_migrations, migrate, schema_version

# 3.35 brings RETURNING and ALTER TABLE DROP COLUMN. Every supported Python on
# Windows ships a newer SQLite; very old Linux distributions may not.
MIN_SQLITE_VERSION = (3, 35, 0)


class DatabaseUnavailableError(RuntimeError):
    """The database cannot be used safely; the application must not start."""


def check_sqlite_version(version: tuple[int, int, int] = sqlite3.sqlite_version_info) -> None:
    if version < MIN_SQLITE_VERSION:
        needed = ".".join(map(str, MIN_SQLITE_VERSION))
        found = ".".join(map(str, version))
        raise DatabaseUnavailableError(f"SQLite {needed} or newer is required, found {found}.")


def connect(path: Path | str) -> sqlite3.Connection:
    """Open a connection with the settings every connection must have.

    isolation_level=None turns off the sqlite3 module's implicit transactions:
    the application opens and ends transactions itself (see UnitOfWork), so it
    is always clear which statements are committed together.
    """
    conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        # Foreign keys are OFF by default in SQLite and must be enabled per connection.
        conn.execute("PRAGMA foreign_keys = ON")
        # Wait up to 5 s for another writer instead of failing at once.
        conn.execute("PRAGMA busy_timeout = 5000")
        # FULL: a committed transaction survives a power cut. Writes are rare, so it is cheap.
        conn.execute("PRAGMA synchronous = FULL")
    except sqlite3.Error:
        conn.close()  # e.g. the file is not a database: do not leak the handle
        raise
    return conn


def quick_check(conn: sqlite3.Connection) -> bool:
    row = conn.execute("PRAGMA quick_check").fetchone()
    return row is not None and row[0] == "ok"


def initialise_database(path: Path, *, before_upgrade: Callable[[int], None] | None = None) -> int:
    """Create or upgrade the database and verify it. Returns the schema version.

    `before_upgrade(current_version)` is called when an existing database is about
    to be migrated, so a backup can be taken first.
    """
    check_sqlite_version()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        # Write-ahead logging: readers never block the writer. The setting is
        # stored in the database file, so it only needs to be set once.
        conn.execute("PRAGMA journal_mode = WAL")
        if not quick_check(conn):
            raise DatabaseUnavailableError(
                f"The database {path} failed its integrity check. Restore it from a backup."
            )
        current = schema_version(conn)
        pending = [m for m in discover_migrations() if m.version > current]
        if current > 0 and pending and before_upgrade is not None:
            before_upgrade(current)
        migrate(conn)
        return schema_version(conn)
    finally:
        conn.close()

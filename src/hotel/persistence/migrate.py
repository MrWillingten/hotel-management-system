"""Versioned schema migrations.

Each file in persistence/migrations is named NNNN_description.sql. The number
of the last applied migration is stored in SQLite's built-in
`PRAGMA user_version`, so on start-up only the newer files are applied, each
inside its own transaction: a failing migration leaves the schema untouched.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from importlib import resources

_MIGRATIONS_PACKAGE = "hotel.persistence.migrations"
_FILENAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str


def discover_migrations() -> list[Migration]:
    found = []
    for entry in resources.files(_MIGRATIONS_PACKAGE).iterdir():
        match = _FILENAME.match(entry.name)
        if match:
            found.append(Migration(int(match.group(1)), entry.name, entry.read_text("utf-8")))
    found.sort(key=lambda m: m.version)
    expected = list(range(1, len(found) + 1))
    if [m.version for m in found] != expected:
        raise MigrationError("Migration numbers must start at 0001 and have no gaps.")
    return found


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection, migrations: list[Migration] | None = None) -> list[int]:
    """Apply pending migrations in order. Returns the versions that were applied."""
    migrations = discover_migrations() if migrations is None else migrations
    current = schema_version(conn)
    if migrations and current > migrations[-1].version:
        raise MigrationError(
            f"The database is at schema version {current}, newer than this program "
            f"({migrations[-1].version}). Use a newer version of the application."
        )
    applied = []
    for migration in migrations:
        if migration.version <= current:
            continue
        # executescript() runs several statements at once. The version number is an
        # int taken from our own file name, never user input.
        script = (
            "BEGIN IMMEDIATE;\n"
            f"{migration.sql}\n"
            f"PRAGMA user_version = {migration.version:d};\n"
            "COMMIT;"
        )
        try:
            conn.executescript(script)
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationError(f"Migration {migration.name} failed: {exc}") from exc
        applied.append(migration.version)
    return applied

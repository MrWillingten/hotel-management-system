"""Consistent backups of the live database.

Copying hotel.db with the file manager while the application runs can produce
a broken copy: recent changes may still sit in the separate write-ahead log
(hotel.db-wal). SQLite's online backup API copies a consistent snapshot even
while the database is in use, so that is the only method used here.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hotel.persistence.db import connect, quick_check
from hotel.persistence.migrate import discover_migrations

_NAME = re.compile(r"^hotel-(\d{8}-\d{6})(?:-([a-z0-9-]+))?(?:-\d+)?\.db$")


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BackupFile:
    path: Path
    created_at: datetime  # local hotel time, as written in the file name
    label: str
    size: int

    @property
    def name(self) -> str:
        return self.path.name


def _verify(path: Path) -> int:
    """Check a database file and return its schema version."""
    conn = sqlite3.connect(path)
    try:
        if not quick_check(conn):
            raise BackupError(f"{path.name} failed its integrity check")
        return conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"{path.name} is not a valid database: {exc}") from exc
    finally:
        conn.close()


def create_backup(db_path: Path, backup_dir: Path, now: datetime, *, label: str = "manual") -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stem = f"hotel-{now:%Y%m%d-%H%M%S}-{label}"
    final = backup_dir / f"{stem}.db"
    counter = 1
    while final.exists():
        final = backup_dir / f"{stem}-{counter}.db"
        counter += 1
    partial = final.with_suffix(".partial")
    source = connect(db_path)
    target = sqlite3.connect(partial)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    try:
        _verify(partial)
    except BackupError:
        partial.unlink(missing_ok=True)
        raise
    # Renaming is atomic: a backup file is either complete or absent, never half-written.
    os.replace(partial, final)
    return final


def list_backups(backup_dir: Path) -> list[BackupFile]:
    if not backup_dir.is_dir():
        return []
    found = []
    for path in backup_dir.iterdir():
        match = _NAME.match(path.name)
        if match and path.is_file():
            created = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")  # noqa: DTZ007 - local
            found.append(BackupFile(path, created, match.group(2) or "", path.stat().st_size))
    return sorted(found, key=lambda b: (b.created_at, b.name), reverse=True)


def rotate(backup_dir: Path, *, label: str, keep: int) -> list[Path]:
    """Delete the oldest backups with this label, keeping the `keep` newest."""
    same_label = [b for b in list_backups(backup_dir) if b.label == label]
    removed = []
    for old in same_label[keep:]:
        old.path.unlink()
        removed.append(old.path)
    return removed


def restore_backup(db_path: Path, backup: Path, backup_dir: Path, now: datetime) -> Path:
    """Replace the database with `backup`. Returns the copy made of the replaced database.

    The application must be stopped while this runs.
    """
    if not backup.is_file():
        raise BackupError(f"{backup} does not exist")
    version = _verify(backup)
    newest_known = discover_migrations()[-1].version
    if version > newest_known:
        raise BackupError(
            f"{backup.name} was made by a newer version of the application (schema {version})"
        )
    safety_copy = create_backup(db_path, backup_dir, now, label="pre-restore")
    source = sqlite3.connect(backup)
    target = connect(db_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return safety_copy

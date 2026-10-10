"""Converting Python values to and from their SQLite text form.

Python 3.12 deprecated the sqlite3 module's automatic date adapters, and they
never handled time zones well, so conversions are explicit.
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def datetime_to_db(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("Refusing to store a naive datetime; use timezone-aware UTC values")
    # Always include microseconds: isoformat() drops them when they are zero,
    # and strings of different lengths would no longer sort chronologically.
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def datetime_from_db(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def date_to_db(value: date) -> str:
    return value.isoformat()


def date_from_db(value: str) -> date:
    return date.fromisoformat(value)

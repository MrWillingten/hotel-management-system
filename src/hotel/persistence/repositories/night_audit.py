from __future__ import annotations

import sqlite3
from datetime import date

from hotel.domain.money import Money
from hotel.domain.night_audit import DailySnapshot
from hotel.persistence.convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_SELECT = (
    "SELECT s.day, s.nights_sold, s.nights_sellable, s.room_value_mill, s.invoiced_mill, "
    "s.cash_mill, s.reservations_made, s.cancellations, s.no_shows, s.overdue_departures, "
    "s.created_at, COALESCE(u.full_name, '') AS created_by_name "
    "FROM daily_snapshot s LEFT JOIN app_user u ON u.id = s.created_by"
)


def _to_snapshot(row: sqlite3.Row) -> DailySnapshot:
    return DailySnapshot(
        day=date_from_db(row["day"]),
        nights_sold=row["nights_sold"],
        nights_sellable=row["nights_sellable"],
        room_value=Money(row["room_value_mill"]),
        invoiced=Money(row["invoiced_mill"]),
        cash=Money(row["cash_mill"]),
        reservations_made=row["reservations_made"],
        cancellations=row["cancellations"],
        no_shows=row["no_shows"],
        overdue_departures=row["overdue_departures"],
        created_at=datetime_from_db(row["created_at"]),
        created_by_name=row["created_by_name"],
    )


class SnapshotRepository(BaseRepository):
    def get(self, day: date) -> DailySnapshot | None:
        row = self._fetch_one(f"{_SELECT} WHERE s.day = ?", (date_to_db(day),))
        return _to_snapshot(row) if row else None

    def last_closed_day(self) -> date | None:
        row = self._fetch_one("SELECT MAX(day) FROM daily_snapshot")
        return date_from_db(row[0]) if row and row[0] else None

    def recent(self, limit: int = 60) -> list[DailySnapshot]:
        rows = self._fetch_all(f"{_SELECT} ORDER BY s.day DESC LIMIT ?", (limit,))
        return [_to_snapshot(r) for r in rows]

    def add(self, snapshot: DailySnapshot, created_by: int | None) -> bool:
        """Insert unless the day is already closed; returns True if this call closed it."""
        cursor = self._execute(
            "INSERT INTO daily_snapshot (day, nights_sold, nights_sellable, room_value_mill, "
            "invoiced_mill, cash_mill, reservations_made, cancellations, no_shows, "
            "overdue_departures, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (day) DO NOTHING",
            (
                date_to_db(snapshot.day),
                snapshot.nights_sold,
                snapshot.nights_sellable,
                snapshot.room_value.millimes,
                snapshot.invoiced.millimes,
                snapshot.cash.millimes,
                snapshot.reservations_made,
                snapshot.cancellations,
                snapshot.no_shows,
                snapshot.overdue_departures,
                datetime_to_db(snapshot.created_at),
                created_by,
            ),
        )
        return cursor.rowcount == 1

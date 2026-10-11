from __future__ import annotations

import sqlite3

from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.pricing import RatePeriod
from hotel.persistence.convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_SELECT = (
    "SELECT p.id, p.category_id, p.name, p.start_date, p.end_date, p.rate_mill, p.created_at, "
    "c.name AS category_name FROM rate_period p JOIN room_category c ON c.id = p.category_id"
)


def _to_period(row: sqlite3.Row) -> RatePeriod:
    return RatePeriod(
        id=row["id"],
        category_id=row["category_id"],
        name=row["name"],
        period=StayPeriod(date_from_db(row["start_date"]), date_from_db(row["end_date"])),
        nightly_rate=Money(row["rate_mill"]),
        category_name=row["category_name"],
        created_at=datetime_from_db(row["created_at"]),
    )


class RatePeriodRepository(BaseRepository):
    def list(self) -> list[RatePeriod]:
        rows = self._fetch_all(f"{_SELECT} ORDER BY p.start_date, c.name")
        return [_to_period(r) for r in rows]

    def get(self, period_id: int) -> RatePeriod | None:
        row = self._fetch_one(f"{_SELECT} WHERE p.id = ?", (period_id,))
        return _to_period(row) if row else None

    def overlapping(self, category_id: int, period: StayPeriod) -> list[RatePeriod]:
        """Half-open overlap test, as for stays: a1 < d2 and a2 < d1."""
        rows = self._fetch_all(
            f"{_SELECT} WHERE p.category_id = ? AND p.start_date < ? AND ? < p.end_date",
            (category_id, date_to_db(period.departure), date_to_db(period.arrival)),
        )
        return [_to_period(r) for r in rows]

    def add(self, rate: RatePeriod) -> int:
        cursor = self._execute(
            "INSERT INTO rate_period (category_id, name, start_date, end_date, rate_mill, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                rate.category_id,
                rate.name,
                date_to_db(rate.period.arrival),
                date_to_db(rate.period.departure),
                rate.nightly_rate.millimes,
                datetime_to_db(rate.created_at),
            ),
        )
        return cursor.lastrowid

    def delete(self, period_id: int) -> None:
        self._execute("DELETE FROM rate_period WHERE id = ?", (period_id,))

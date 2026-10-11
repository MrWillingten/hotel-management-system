"""Read-only aggregate queries for the management reports (story 5.1).

Every query is a fixed string with `?` parameters; `GROUP BY` makes SQLite do
the counting and summing instead of loading every row into Python.
Instants are compared as UTC text (the stored format sorts chronologically).
"""

from __future__ import annotations

from datetime import date, datetime

from hotel.domain.money import Money
from hotel.domain.reports import CategoryFigures, Count
from hotel.persistence.convert import date_from_db, date_to_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_SOLD_PER_NIGHT = (
    "SELECT night, COUNT(*) AS sold, SUM(rate_mill) AS value FROM room_night "
    "WHERE reservation_id IS NOT NULL AND night >= ? AND night <= ? GROUP BY night"
)
# Maintenance only reduces what can be sold when the room is in service at all.
_CLOSED_PER_NIGHT = (
    "SELECT n.night, COUNT(*) AS closed FROM room_night n JOIN room r ON r.id = n.room_id "
    "WHERE n.maintenance_id IS NOT NULL AND r.in_service = 1 AND n.night >= ? AND n.night <= ? "
    "GROUP BY n.night"
)
_BY_CATEGORY = (
    "SELECT c.name, COUNT(*) AS nights, SUM(n.rate_mill) AS value FROM room_night n "
    "JOIN room r ON r.id = n.room_id JOIN room_category c ON c.id = r.category_id "
    "WHERE n.reservation_id IS NOT NULL AND n.night >= ? AND n.night <= ? "
    "GROUP BY c.id ORDER BY nights DESC, c.name"
)
_INVOICED = (
    "SELECT l.kind, SUM(l.amount_mill) AS amount FROM invoice_line l "
    "JOIN invoice i ON i.id = l.invoice_id WHERE i.issued_at >= ? AND i.issued_at < ? "
    "GROUP BY l.kind"
)
_CASH = (
    "SELECT method, SUM(CASE kind WHEN 'REFUND' THEN -amount_mill ELSE amount_mill END) AS net "
    "FROM payment WHERE paid_at >= ? AND paid_at < ? GROUP BY method"
)


class ReportRepository(BaseRepository):
    def rooms_in_service(self) -> int:
        return self._fetch_one("SELECT COUNT(*) FROM room WHERE in_service = 1")[0]

    def sold_per_night(self, first: date, last: date) -> dict[date, tuple[int, Money]]:
        rows = self._fetch_all(_SOLD_PER_NIGHT, (date_to_db(first), date_to_db(last)))
        return {date_from_db(r["night"]): (r["sold"], Money(r["value"])) for r in rows}

    def closed_per_night(self, first: date, last: date) -> dict[date, int]:
        rows = self._fetch_all(_CLOSED_PER_NIGHT, (date_to_db(first), date_to_db(last)))
        return {date_from_db(r["night"]): r["closed"] for r in rows}

    def by_category(self, first: date, last: date) -> list[CategoryFigures]:
        rows = self._fetch_all(_BY_CATEGORY, (date_to_db(first), date_to_db(last)))
        return [CategoryFigures(r["name"], r["nights"], Money(r["value"])) for r in rows]

    def reservations_made(self, start: datetime, end: datetime) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM reservation WHERE created_at >= ? AND created_at < ?",
            (datetime_to_db(start), datetime_to_db(end)),
        )[0]

    def cancellations(self, start: datetime, end: datetime) -> Count:
        return self._count(
            "SELECT COUNT(*), COALESCE(SUM(cancellation_fee_mill), 0) FROM reservation "
            "WHERE status = 'CANCELLED' AND cancelled_at >= ? AND cancelled_at < ?",
            start,
            end,
        )

    def no_shows(self, start: datetime, end: datetime) -> Count:
        return self._count(
            "SELECT COUNT(*), COALESCE(SUM(cancellation_fee_mill), 0) FROM reservation "
            "WHERE status = 'NO_SHOW' AND no_show_at >= ? AND no_show_at < ?",
            start,
            end,
        )

    def invoice_count(self, start: datetime, end: datetime) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM invoice WHERE issued_at >= ? AND issued_at < ?",
            (datetime_to_db(start), datetime_to_db(end)),
        )[0]

    def invoiced(self, start: datetime, end: datetime) -> dict[str, Money]:
        rows = self._fetch_all(_INVOICED, (datetime_to_db(start), datetime_to_db(end)))
        return {r["kind"]: Money(r["amount"]) for r in rows}

    def cash(self, start: datetime, end: datetime) -> dict[str, Money]:
        rows = self._fetch_all(_CASH, (datetime_to_db(start), datetime_to_db(end)))
        return {r["method"]: Money(r["net"]) for r in rows}

    def _count(self, sql: str, start: datetime, end: datetime) -> Count:
        row = self._fetch_one(sql, (datetime_to_db(start), datetime_to_db(end)))
        return Count(row[0], Money(row[1]))

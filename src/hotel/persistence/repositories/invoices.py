from __future__ import annotations

import sqlite3

from hotel.domain.billing import BillLine, LineKind
from hotel.domain.invoices import Invoice
from hotel.domain.money import Money
from hotel.domain.paging import Page, PageRequest
from hotel.persistence.convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository, escape_like
from hotel.persistence.repositories.billing import PaymentRepository

_SELECT = (
    "SELECT i.id, i.number, i.reservation_id, i.reservation_code, i.guest_name, i.arrival, "
    "i.departure, i.issued_at, COALESCE(u.full_name, '') AS issued_by_name, i.total_mill, "
    "i.balance_mill FROM invoice i LEFT JOIN app_user u ON u.id = i.issued_by"
)
_LINES = (
    "SELECT kind, label, quantity, unit_mill, amount_mill, first_date, last_date, rate_bp "
    "FROM invoice_line WHERE invoice_id = ? ORDER BY line_no"
)
_SEARCH_WHERE = " WHERE i.number LIKE ? ESCAPE '\\' OR i.guest_name LIKE ? ESCAPE '\\'"
_COUNT = "SELECT COUNT(*) FROM invoice i{where}"
_PAGE = _SELECT + "{where} ORDER BY i.issued_at DESC, i.id DESC LIMIT ? OFFSET ?"
# Closed stays whose invoice is not fully paid yet, payments made since included.
_UNPAID = (
    "SELECT i.reservation_id, i.number, i.guest_name, i.total_mill - COALESCE(("
    "SELECT SUM(CASE p.kind WHEN 'REFUND' THEN -p.amount_mill ELSE p.amount_mill END) "
    "FROM payment p WHERE p.reservation_id = i.reservation_id), 0) AS due_mill "
    "FROM invoice i WHERE due_mill > 0 ORDER BY i.issued_at"
)


class InvoiceRepository(BaseRepository):
    def add(self, invoice: Invoice, issued_by: int | None) -> Invoice:
        bill = invoice.bill
        cursor = self._execute(
            "INSERT INTO invoice (number, reservation_id, reservation_code, guest_name, arrival, "
            "departure, issued_at, issued_by, subtotal_mill, discount_mill, tax_mill, total_mill, "
            "paid_mill, balance_mill) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                invoice.number,
                invoice.reservation_id,
                invoice.reservation_code,
                invoice.guest_name,
                date_to_db(invoice.arrival),
                date_to_db(invoice.departure),
                datetime_to_db(invoice.issued_at),
                issued_by,
                bill.subtotal.millimes,
                bill.discount.millimes,
                bill.tax.millimes,
                bill.total.millimes,
                bill.paid.millimes,
                bill.balance.millimes,
            ),
        )
        invoice_id = cursor.lastrowid
        self._conn.executemany(
            "INSERT INTO invoice_line (invoice_id, line_no, kind, label, quantity, unit_mill, "
            "amount_mill, first_date, last_date, rate_bp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    invoice_id,
                    number,
                    line.kind.value,
                    line.label,
                    line.quantity,
                    line.unit.millimes,
                    line.amount.millimes,
                    date_to_db(line.first) if line.first else None,
                    date_to_db(line.last) if line.last else None,
                    line.rate_bp,
                )
                for number, line in enumerate(invoice.lines, start=1)
            ],
        )
        return self.get(invoice_id)

    def get(self, invoice_id: int) -> Invoice | None:
        row = self._fetch_one(f"{_SELECT} WHERE i.id = ?", (invoice_id,))
        return self._with_details(row) if row else None

    def for_reservation(self, reservation_id: int) -> Invoice | None:
        row = self._fetch_one(f"{_SELECT} WHERE i.reservation_id = ?", (reservation_id,))
        return self._with_details(row) if row else None

    def search(self, query: str, request: PageRequest) -> Page[Invoice]:
        where, params = "", []
        if query:
            where = _SEARCH_WHERE
            pattern = f"%{escape_like(query)}%"
            params = [pattern, pattern]
        total = self._fetch_one(_COUNT.format(where=where), params)[0]
        rows = self._fetch_all(
            _PAGE.format(where=where), [*params, request.per_page, request.offset]
        )
        return Page([self._header(r) for r in rows], total, request)

    def unpaid(self) -> list[tuple[int, str, str, Money]]:
        """(reservation_id, invoice number, guest, amount still due) after check-out."""
        return [
            (r["reservation_id"], r["number"], r["guest_name"], Money(r["due_mill"]))
            for r in self._fetch_all(_UNPAID)
        ]

    # ------------------------------------------------------------ mapping
    @staticmethod
    def _header(row: sqlite3.Row, lines=None, payments=None) -> Invoice:
        return Invoice(
            id=row["id"],
            number=row["number"],
            reservation_id=row["reservation_id"],
            reservation_code=row["reservation_code"],
            guest_name=row["guest_name"],
            arrival=date_from_db(row["arrival"]),
            departure=date_from_db(row["departure"]),
            issued_at=datetime_from_db(row["issued_at"]),
            issued_by_name=row["issued_by_name"],
            lines=lines or [],
            payments=payments or [],
            listed_total=Money(row["total_mill"]),
        )

    def _with_details(self, row: sqlite3.Row) -> Invoice:
        lines = [
            BillLine(
                LineKind(r["kind"]),
                r["label"],
                r["quantity"],
                Money(r["unit_mill"]),
                Money(r["amount_mill"]),
                date_from_db(r["first_date"]) if r["first_date"] else None,
                date_from_db(r["last_date"]) if r["last_date"] else None,
                r["rate_bp"],
            )
            for r in self._fetch_all(_LINES, (row["id"],))
        ]
        issued_at = datetime_from_db(row["issued_at"])
        payments = [
            p
            for p in PaymentRepository(self._conn).for_reservation(row["reservation_id"])
            if p.paid_at <= issued_at
        ]
        invoice = self._header(row, lines, payments)
        if invoice.total.millimes != row["total_mill"]:
            # Cannot happen through the application (triggers forbid changes):
            # it would mean the file was edited by hand.
            raise RuntimeError(f"Invoice {invoice.number}: lines do not add up to the total")
        return invoice

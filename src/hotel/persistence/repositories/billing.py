from __future__ import annotations

import sqlite3

from hotel.domain.billing import (
    Discount,
    FixedDiscount,
    Payment,
    PaymentKind,
    PaymentMethod,
    PercentDiscount,
)
from hotel.domain.errors import StaleDataError
from hotel.domain.money import Money
from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_DISCOUNT = (
    "SELECT d.id, d.reservation_id, d.kind, d.rate_bp, d.amount_mill, d.reason, d.approved_by, "
    "d.created_at, d.removed_at, COALESCE(u.full_name, '') AS approved_by_name "
    "FROM discount d LEFT JOIN app_user u ON u.id = d.approved_by"
)
_PAYMENT = (
    "SELECT p.id, p.reservation_id, p.kind, p.method, p.amount_mill, p.reference, p.paid_at, "
    "p.recorded_by, COALESCE(u.full_name, '') AS recorded_by_name "
    "FROM payment p LEFT JOIN app_user u ON u.id = p.recorded_by"
)


def _to_discount(row: sqlite3.Row) -> Discount:
    common = {
        "id": row["id"],
        "reservation_id": row["reservation_id"],
        "reason": row["reason"],
        "approved_by": row["approved_by"],
        "approved_by_name": row["approved_by_name"],
        "created_at": datetime_from_db(row["created_at"]),
        "removed_at": datetime_from_db(row["removed_at"]),
    }
    if row["kind"] == "PERCENT":
        return PercentDiscount(rate_bp=row["rate_bp"], **common)
    return FixedDiscount(value=Money(row["amount_mill"]), **common)


def _to_payment(row: sqlite3.Row) -> Payment:
    return Payment(
        id=row["id"],
        reservation_id=row["reservation_id"],
        kind=PaymentKind(row["kind"]),
        method=PaymentMethod(row["method"]),
        amount=Money(row["amount_mill"]),
        paid_at=datetime_from_db(row["paid_at"]),
        reference=row["reference"],
        recorded_by=row["recorded_by"],
        recorded_by_name=row["recorded_by_name"],
    )


class DiscountRepository(BaseRepository):
    def for_reservation(self, reservation_id: int) -> list[Discount]:
        rows = self._fetch_all(
            f"{_DISCOUNT} WHERE d.reservation_id = ? ORDER BY d.id", (reservation_id,)
        )
        return [_to_discount(r) for r in rows]

    def get(self, discount_id: int) -> Discount | None:
        row = self._fetch_one(f"{_DISCOUNT} WHERE d.id = ?", (discount_id,))
        return _to_discount(row) if row else None

    def add(self, discount: Discount) -> Discount:
        is_percent = isinstance(discount, PercentDiscount)
        cursor = self._execute(
            "INSERT INTO discount (reservation_id, kind, rate_bp, amount_mill, reason, "
            "approved_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                discount.reservation_id,
                "PERCENT" if is_percent else "FIXED",
                discount.rate_bp if is_percent else None,
                None if is_percent else discount.value.millimes,
                discount.reason,
                discount.approved_by,
                datetime_to_db(discount.created_at),
            ),
        )
        discount.id = cursor.lastrowid
        return discount

    def remove(self, discount: Discount, removed_by: int | None) -> None:
        cursor = self._execute(
            "UPDATE discount SET removed_at = ?, removed_by = ? "
            "WHERE id = ? AND removed_at IS NULL",
            (datetime_to_db(discount.removed_at), removed_by, discount.id),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="discount", id=discount.id)


class PaymentRepository(BaseRepository):
    def for_reservation(self, reservation_id: int) -> list[Payment]:
        rows = self._fetch_all(
            f"{_PAYMENT} WHERE p.reservation_id = ? ORDER BY p.paid_at, p.id", (reservation_id,)
        )
        return [_to_payment(r) for r in rows]

    def add(self, payment: Payment) -> Payment:
        cursor = self._execute(
            "INSERT INTO payment (reservation_id, kind, method, amount_mill, reference, paid_at, "
            "recorded_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                payment.reservation_id,
                payment.kind.value,
                payment.method.value,
                payment.amount.millimes,
                payment.reference,
                datetime_to_db(payment.paid_at),
                payment.recorded_by,
            ),
        )
        payment.id = cursor.lastrowid
        return payment

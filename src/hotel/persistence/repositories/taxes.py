from __future__ import annotations

import sqlite3

from hotel.domain.errors import ConflictError, StaleDataError
from hotel.domain.money import Money
from hotel.domain.taxes import (
    PerAdultNightTax,
    PercentTax,
    TaxBase,
    TaxExemption,
    TaxKind,
    TaxPayers,
    TaxRule,
)
from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_SELECT = (
    "SELECT id, name, kind, rate_bp, amount_mill, applies_to, payers, is_active, version "
    "FROM tax_rule"
)


def _to_rule(row: sqlite3.Row) -> TaxRule:
    common = {
        "id": row["id"],
        "name": row["name"],
        "applies_to": TaxBase(row["applies_to"]),
        "payers": TaxPayers(row["payers"]),
        "is_active": bool(row["is_active"]),
        "version": row["version"],
    }
    if row["kind"] == TaxKind.PERCENT:
        return PercentTax(rate_bp=row["rate_bp"], **common)
    return PerAdultNightTax(amount_per=Money(row["amount_mill"]), **common)


def _values(rule: TaxRule) -> tuple:
    rate = rule.rate_bp if isinstance(rule, PercentTax) else None
    amount = rule.amount_per.millimes if isinstance(rule, PerAdultNightTax) else None
    return (
        rule.name,
        rule.kind.value,
        rate,
        amount,
        rule.applies_to.value,
        rule.payers.value,
        int(rule.is_active),
    )


class TaxRuleRepository(BaseRepository):
    def list(self, *, active_only: bool = False) -> list[TaxRule]:
        where = " WHERE is_active = 1" if active_only else ""
        rows = self._fetch_all(f"{_SELECT}{where} ORDER BY is_active DESC, id")
        return [_to_rule(r) for r in rows]

    def get(self, rule_id: int) -> TaxRule | None:
        row = self._fetch_one(f"{_SELECT} WHERE id = ?", (rule_id,))
        return _to_rule(row) if row else None

    def add(self, rule: TaxRule) -> TaxRule:
        cursor = self._execute(
            "INSERT INTO tax_rule (name, kind, rate_bp, amount_mill, applies_to, payers, "
            "is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            _values(rule),
        )
        rule.id = cursor.lastrowid
        return rule

    def update(self, rule: TaxRule) -> None:
        cursor = self._execute(
            "UPDATE tax_rule SET name = ?, kind = ?, rate_bp = ?, amount_mill = ?, applies_to = ?, "
            "payers = ?, is_active = ?, version = version + 1 WHERE id = ? AND version = ?",
            (*_values(rule), rule.id, rule.version),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="tax_rule", id=rule.id)
        rule.version += 1


_EXEMPTIONS = (
    "SELECT e.id, e.reservation_id, e.tax_rule_id, e.reason, e.created_at, "
    "u.full_name AS created_by_name, t.name AS tax_name FROM tax_exemption e "
    "JOIN tax_rule t ON t.id = e.tax_rule_id LEFT JOIN app_user u ON u.id = e.created_by "
)


def _to_exemption(row: sqlite3.Row) -> TaxExemption:
    return TaxExemption(
        id=row["id"],
        reservation_id=row["reservation_id"],
        tax_rule_id=row["tax_rule_id"],
        reason=row["reason"],
        created_at=datetime_from_db(row["created_at"]),
        created_by_name=row["created_by_name"] or "",
        tax_name=row["tax_name"],
    )


class TaxExemptionRepository(BaseRepository):
    def for_reservation(self, reservation_id: int) -> list[TaxExemption]:
        rows = self._fetch_all(
            _EXEMPTIONS + "WHERE e.reservation_id = ? ORDER BY e.id", (reservation_id,)
        )
        return [_to_exemption(r) for r in rows]

    def get(self, exemption_id: int) -> TaxExemption | None:
        row = self._fetch_one(_EXEMPTIONS + "WHERE e.id = ?", (exemption_id,))
        return _to_exemption(row) if row else None

    def add(self, exemption: TaxExemption, created_by: int | None) -> TaxExemption:
        try:
            cursor = self._execute(
                "INSERT INTO tax_exemption (reservation_id, tax_rule_id, reason, created_at, "
                "created_by) VALUES (?, ?, ?, ?, ?)",
                (
                    exemption.reservation_id,
                    exemption.tax_rule_id,
                    exemption.reason,
                    datetime_to_db(exemption.created_at),
                    created_by,
                ),
            )
        except sqlite3.IntegrityError as exc:  # UNIQUE(reservation_id, tax_rule_id)
            raise ConflictError("tax.already_exempt") from exc
        exemption.id = cursor.lastrowid
        return exemption

    def delete(self, exemption_id: int) -> None:
        self._execute("DELETE FROM tax_exemption WHERE id = ?", (exemption_id,))

    def count_for_rule(self, rule_id: int) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM tax_exemption WHERE tax_rule_id = ?", (rule_id,)
        )[0]

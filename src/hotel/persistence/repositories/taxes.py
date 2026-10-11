from __future__ import annotations

import sqlite3

from hotel.domain.errors import StaleDataError
from hotel.domain.money import Money
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxBase, TaxKind, TaxRule
from hotel.persistence.repositories.base import BaseRepository

_SELECT = (
    "SELECT id, name, kind, rate_bp, amount_mill, applies_to, is_active, version FROM tax_rule"
)


def _to_rule(row: sqlite3.Row) -> TaxRule:
    common = {
        "id": row["id"],
        "name": row["name"],
        "applies_to": TaxBase(row["applies_to"]),
        "is_active": bool(row["is_active"]),
        "version": row["version"],
    }
    if row["kind"] == TaxKind.PERCENT:
        return PercentTax(rate_bp=row["rate_bp"], **common)
    return PerAdultNightTax(amount_per=Money(row["amount_mill"]), **common)


def _values(rule: TaxRule) -> tuple:
    rate = rule.rate_bp if isinstance(rule, PercentTax) else None
    amount = rule.amount_per.millimes if isinstance(rule, PerAdultNightTax) else None
    return (rule.name, rule.kind.value, rate, amount, rule.applies_to.value, int(rule.is_active))


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
            "INSERT INTO tax_rule (name, kind, rate_bp, amount_mill, applies_to, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            _values(rule),
        )
        rule.id = cursor.lastrowid
        return rule

    def update(self, rule: TaxRule) -> None:
        cursor = self._execute(
            "UPDATE tax_rule SET name = ?, kind = ?, rate_bp = ?, amount_mill = ?, applies_to = ?, "
            "is_active = ?, version = version + 1 WHERE id = ? AND version = ?",
            (*_values(rule), rule.id, rule.version),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="tax_rule", id=rule.id)
        rule.version += 1

from __future__ import annotations

import sqlite3
from datetime import datetime

from hotel.domain.errors import StaleDataError
from hotel.domain.extras import Extra, ServiceCharge
from hotel.domain.money import Money
from hotel.persistence.convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_EXTRA = "SELECT id, name, unit_price_mill, is_active, version, archived_at FROM extra"
_CHARGE = (
    "SELECT id, reservation_id, extra_id, description, quantity, unit_price_mill, charge_date, "
    "created_by, created_at, voided_at, voided_by, void_reason FROM service_charge"
)


def _to_extra(row: sqlite3.Row) -> Extra:
    return Extra(
        row["id"],
        row["name"],
        Money(row["unit_price_mill"]),
        bool(row["is_active"]),
        row["version"],
        datetime_from_db(row["archived_at"]),
    )


def _to_charge(row: sqlite3.Row) -> ServiceCharge:
    return ServiceCharge(
        id=row["id"],
        reservation_id=row["reservation_id"],
        extra_id=row["extra_id"],
        description=row["description"],
        quantity=row["quantity"],
        unit_price=Money(row["unit_price_mill"]),
        charge_date=date_from_db(row["charge_date"]),
        created_by=row["created_by"],
        created_at=datetime_from_db(row["created_at"]),
        voided_at=datetime_from_db(row["voided_at"]),
        voided_by=row["voided_by"],
        void_reason=row["void_reason"],
    )


class ExtraRepository(BaseRepository):
    def list(self, *, active_only: bool = False, archived: bool = False) -> list[Extra]:
        """The catalogue; archived services (story 6.17) only when asked for, and then alone."""
        if archived:
            rows = self._fetch_all(f"{_EXTRA} WHERE archived_at IS NOT NULL ORDER BY name")
        elif active_only:
            rows = self._fetch_all(f"{_EXTRA} WHERE is_active = 1 ORDER BY name")
        else:
            rows = self._fetch_all(
                f"{_EXTRA} WHERE archived_at IS NULL ORDER BY is_active DESC, name"
            )
        return [_to_extra(r) for r in rows]

    # ------------------------------------------------------------ delete or archive (6.17)
    def count_charges(self, extra_id: int) -> int:
        return self._fetch_one(
            "SELECT COUNT(*) FROM service_charge WHERE extra_id = ?", (extra_id,)
        )[0]

    def count_archived(self) -> int:
        return self._fetch_one("SELECT COUNT(*) FROM extra WHERE archived_at IS NOT NULL")[0]

    def archive(self, extra_id: int, now: datetime | None) -> None:
        """`now` archives (and deactivates), None restores (still inactive)."""
        if now is None:
            self._execute(
                "UPDATE extra SET archived_at = NULL, version = version + 1 WHERE id = ?",
                (extra_id,),
            )
        else:
            self._execute(
                "UPDATE extra SET archived_at = ?, is_active = 0, version = version + 1 "
                "WHERE id = ?",
                (datetime_to_db(now), extra_id),
            )

    def delete(self, extra_id: int) -> None:
        self._execute("DELETE FROM extra WHERE id = ?", (extra_id,))

    def get(self, extra_id: int) -> Extra | None:
        row = self._fetch_one(f"{_EXTRA} WHERE id = ?", (extra_id,))
        return _to_extra(row) if row else None

    def name_taken(self, name: str, *, except_id: int | None = None) -> bool:
        row = self._fetch_one(
            "SELECT 1 FROM extra WHERE name = ? AND id IS NOT ?", (name, except_id)
        )
        return row is not None

    def add(self, extra: Extra) -> Extra:
        cursor = self._execute(
            "INSERT INTO extra (name, unit_price_mill, is_active) VALUES (?, ?, ?)",
            (extra.name, extra.unit_price.millimes, int(extra.is_active)),
        )
        extra.id = cursor.lastrowid
        return extra

    def update(self, extra: Extra) -> None:
        cursor = self._execute(
            "UPDATE extra SET name = ?, unit_price_mill = ?, is_active = ?, version = version + 1 "
            "WHERE id = ? AND version = ?",
            (extra.name, extra.unit_price.millimes, int(extra.is_active), extra.id, extra.version),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="extra", id=extra.id)
        extra.version += 1


class ServiceChargeRepository(BaseRepository):
    def for_reservation(self, reservation_id: int) -> list[ServiceCharge]:
        rows = self._fetch_all(
            f"{_CHARGE} WHERE reservation_id = ? ORDER BY charge_date, id", (reservation_id,)
        )
        return [_to_charge(r) for r in rows]

    def get(self, charge_id: int) -> ServiceCharge | None:
        row = self._fetch_one(f"{_CHARGE} WHERE id = ?", (charge_id,))
        return _to_charge(row) if row else None

    def add(self, charge: ServiceCharge) -> ServiceCharge:
        cursor = self._execute(
            "INSERT INTO service_charge (reservation_id, extra_id, description, quantity, "
            "unit_price_mill, charge_date, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                charge.reservation_id,
                charge.extra_id,
                charge.description,
                charge.quantity,
                charge.unit_price.millimes,
                date_to_db(charge.charge_date),
                charge.created_by,
                datetime_to_db(charge.created_at),
            ),
        )
        charge.id = cursor.lastrowid
        return charge

    def void(self, charge: ServiceCharge) -> None:
        # "voided_at IS NULL" makes voiding twice impossible, even in a race.
        cursor = self._execute(
            "UPDATE service_charge SET voided_at = ?, voided_by = ?, void_reason = ? "
            "WHERE id = ? AND voided_at IS NULL",
            (datetime_to_db(charge.voided_at), charge.voided_by, charge.void_reason, charge.id),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="service_charge", id=charge.id)

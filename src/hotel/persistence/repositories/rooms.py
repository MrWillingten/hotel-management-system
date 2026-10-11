from __future__ import annotations

import sqlite3
from datetime import date

from hotel.domain.errors import StaleDataError
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.rooms import MaintenancePeriod, Room, RoomCategory
from hotel.persistence.convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository

_ROOM_SELECT = (
    "SELECT r.id, r.number, r.category_id, r.capacity, r.nightly_rate_mill, r.in_service, "
    "r.notes, r.version, c.name AS category_name "
    "FROM room r JOIN room_category c ON c.id = r.category_id"
)
_MAINTENANCE_SELECT = (
    "SELECT id, room_id, start_date, end_date, reason, created_by, created_at FROM maintenance"
)


def _to_room(row: sqlite3.Row) -> Room:
    return Room(
        id=row["id"],
        number=row["number"],
        category_id=row["category_id"],
        capacity=row["capacity"],
        nightly_rate=Money(row["nightly_rate_mill"]),
        in_service=bool(row["in_service"]),
        notes=row["notes"],
        version=row["version"],
        category_name=row["category_name"],
    )


def _to_maintenance(row: sqlite3.Row) -> MaintenancePeriod:
    return MaintenancePeriod(
        id=row["id"],
        room_id=row["room_id"],
        period=StayPeriod(date_from_db(row["start_date"]), date_from_db(row["end_date"])),
        reason=row["reason"],
        created_by=row["created_by"],
        created_at=datetime_from_db(row["created_at"]),
    )


class CategoryRepository(BaseRepository):
    def list_all(self) -> list[RoomCategory]:
        rows = self._fetch_all(
            "SELECT c.id, c.name, c.description, c.version, COUNT(r.id) AS room_count "
            "FROM room_category c LEFT JOIN room r ON r.category_id = c.id "
            "GROUP BY c.id ORDER BY c.name"
        )
        return [
            RoomCategory(r["id"], r["name"], r["description"], r["version"], r["room_count"])
            for r in rows
        ]

    def get(self, category_id: int) -> RoomCategory | None:
        row = self._fetch_one(
            "SELECT id, name, description, version FROM room_category WHERE id = ?",
            (category_id,),
        )
        return (
            RoomCategory(row["id"], row["name"], row["description"], row["version"])
            if row
            else None
        )

    def name_taken(self, name: str, *, except_id: int | None = None) -> bool:
        row = self._fetch_one(
            "SELECT 1 FROM room_category WHERE name = ? AND id IS NOT ?", (name, except_id)
        )
        return row is not None

    def add(self, category: RoomCategory) -> RoomCategory:
        cursor = self._execute(
            "INSERT INTO room_category (name, description) VALUES (?, ?)",
            (category.name, category.description),
        )
        category.id = cursor.lastrowid
        return category

    def update(self, category: RoomCategory) -> None:
        cursor = self._execute(
            "UPDATE room_category SET name = ?, description = ?, version = version + 1 "
            "WHERE id = ? AND version = ?",
            (category.name, category.description, category.id, category.version),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="room_category", id=category.id)
        category.version += 1


class RoomRepository(BaseRepository):
    def list(self, *, category_id: int | None = None) -> list[Room]:
        if category_id is None:
            rows = self._fetch_all(f"{_ROOM_SELECT} ORDER BY r.number")
        else:
            rows = self._fetch_all(
                f"{_ROOM_SELECT} WHERE r.category_id = ? ORDER BY r.number",
                (category_id,),
            )
        return [_to_room(r) for r in rows]

    def get(self, room_id: int) -> Room | None:
        row = self._fetch_one(f"{_ROOM_SELECT} WHERE r.id = ?", (room_id,))
        return _to_room(row) if row else None

    def number_taken(self, number: str, *, except_id: int | None = None) -> bool:
        row = self._fetch_one(
            "SELECT 1 FROM room WHERE number = ? AND id IS NOT ?", (number, except_id)
        )
        return row is not None

    def add(self, room: Room) -> Room:
        cursor = self._execute(
            "INSERT INTO room (number, category_id, capacity, nightly_rate_mill, in_service, "
            "notes) VALUES (?, ?, ?, ?, ?, ?)",
            (
                room.number,
                room.category_id,
                room.capacity,
                room.nightly_rate.millimes,
                int(room.in_service),
                room.notes,
            ),
        )
        room.id = cursor.lastrowid
        return room

    def update(self, room: Room) -> None:
        cursor = self._execute(
            "UPDATE room SET number = ?, category_id = ?, capacity = ?, nightly_rate_mill = ?, "
            "in_service = ?, notes = ?, version = version + 1 WHERE id = ? AND version = ?",
            (
                room.number,
                room.category_id,
                room.capacity,
                room.nightly_rate.millimes,
                int(room.in_service),
                room.notes,
                room.id,
                room.version,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="room", id=room.id)
        room.version += 1


class MaintenanceRepository(BaseRepository):
    def add(self, maintenance: MaintenancePeriod) -> MaintenancePeriod:
        cursor = self._execute(
            "INSERT INTO maintenance (room_id, start_date, end_date, reason, created_by, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                maintenance.room_id,
                date_to_db(maintenance.period.arrival),
                date_to_db(maintenance.period.departure),
                maintenance.reason,
                maintenance.created_by,
                datetime_to_db(maintenance.created_at),
            ),
        )
        maintenance_id = cursor.lastrowid
        # One row per night; the (room_id, night) primary key refuses any overlap.
        self._conn.executemany(
            "INSERT INTO room_night (room_id, night, maintenance_id) VALUES (?, ?, ?)",
            [
                (maintenance.room_id, date_to_db(night), maintenance_id)
                for night in maintenance.period.each_night()
            ],
        )
        return MaintenancePeriod(
            maintenance_id,
            maintenance.room_id,
            maintenance.period,
            maintenance.reason,
            maintenance.created_by,
            maintenance.created_at,
        )

    def get(self, maintenance_id: int) -> MaintenancePeriod | None:
        row = self._fetch_one(f"{_MAINTENANCE_SELECT} WHERE id = ?", (maintenance_id,))
        return _to_maintenance(row) if row else None

    def list_for_room(self, room_id: int) -> list[MaintenancePeriod]:
        rows = self._fetch_all(
            f"{_MAINTENANCE_SELECT} WHERE room_id = ? ORDER BY start_date DESC",
            (room_id,),
        )
        return [_to_maintenance(r) for r in rows]

    def blocked_nights(self, room_id: int, period: StayPeriod) -> list[date]:
        """Nights of `period` on which the room is already blocked."""
        rows = self._fetch_all(
            "SELECT night FROM room_night WHERE room_id = ? AND night >= ? AND night < ? "
            "ORDER BY night",
            (room_id, date_to_db(period.arrival), date_to_db(period.departure)),
        )
        return [date_from_db(r["night"]) for r in rows]

    def rooms_under_maintenance_on(self, night: date) -> set[int]:
        rows = self._fetch_all(
            "SELECT room_id FROM room_night WHERE night = ?", (date_to_db(night),)
        )
        return {r["room_id"] for r in rows}

    def delete(self, maintenance_id: int) -> None:
        self._execute("DELETE FROM maintenance WHERE id = ?", (maintenance_id,))

    def end_early(self, maintenance_id: int, reopens_on: date) -> None:
        """Shorten an ongoing period so the room is available again from `reopens_on`."""
        self._execute(
            "DELETE FROM room_night WHERE maintenance_id = ? AND night >= ?",
            (maintenance_id, date_to_db(reopens_on)),
        )
        self._execute(
            "UPDATE maintenance SET end_date = ? WHERE id = ?",
            (date_to_db(reopens_on), maintenance_id),
        )

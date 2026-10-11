from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from hotel.domain.errors import ConflictError, StaleDataError
from hotel.domain.money import Money
from hotel.domain.paging import Page, PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import (
    BookedRoom,
    Reservation,
    ReservationStatus,
    RoomNight,
)
from hotel.persistence.convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository, escape_like

_SELECT = (
    "SELECT r.id, r.code, r.guest_id, r.arrival, r.departure, r.status, r.cancellation_fee_mill, "
    "r.notes, r.created_by, r.created_at, r.cancelled_at, r.checked_in_at, r.checked_out_at, "
    "r.no_show_at, r.version, g.first_name || ' ' || g.last_name AS guest_name "
    "FROM reservation r JOIN guest g ON g.id = r.guest_id"
)

# Query templates. Only fixed SQL fragments (a WHERE built from constant
# clauses, or a run of "?" markers) are ever inserted with .format(); every
# value still travels separately as a parameter.
_ROOMS_OF = (
    "SELECT rr.reservation_id, rr.room_id, rr.adults, rr.children, rm.number, "
    "c.name AS category_name FROM reservation_room rr "
    "JOIN room rm ON rm.id = rr.room_id JOIN room_category c ON c.id = rm.category_id "
    "WHERE rr.reservation_id IN ({marks}) ORDER BY rm.number"
)
_NIGHTS_OF = (
    "SELECT reservation_id, room_id, night, rate_mill FROM room_night "
    "WHERE reservation_id IN ({marks}) ORDER BY night, room_id"
)
_COUNT = "SELECT COUNT(*) FROM reservation r JOIN guest g ON g.id = r.guest_id{where}"
_PAGE = _SELECT + "{where} ORDER BY r.arrival DESC, r.id DESC LIMIT ? OFFSET ?"
_FUTURE_FOR_ROOM = (
    "{select} WHERE r.status IN ('CONFIRMED', 'CHECKED_IN') AND r.id IN ("
    "SELECT reservation_id FROM room_night WHERE room_id = ? AND night >= ? "
    "AND reservation_id IS NOT NULL) ORDER BY r.arrival"
)

# Front-desk lists: fixed WHERE and ORDER BY fragments, never user input.
_LISTED = "{select} WHERE {where} ORDER BY {order}"
_WHERE_ARRIVING = "r.status = 'CONFIRMED' AND r.arrival <= ? AND r.departure > ?"
_WHERE_LEAVING = "r.status = 'CHECKED_IN' AND r.departure <= ?"
_WHERE_IN_HOUSE = "r.status = 'CHECKED_IN'"
_BY_ARRIVAL = "r.arrival, r.code"
_BY_DEPARTURE = "r.departure, r.code"


@dataclass(frozen=True, slots=True)
class BlockedNight:
    """A room-night that is not free, and why (used by the availability grid)."""

    room_id: int
    night: date
    reservation_id: int | None
    maintenance_id: int | None
    status: str | None  # reservation status, if any
    code: str | None
    guest_name: str | None
    arrival: date | None


@dataclass(frozen=True, slots=True)
class ReservationFilter:
    query: str = ""  # code or guest name
    status: ReservationStatus | None = None
    arriving_from: date | None = None
    arriving_until: date | None = None


def _to_reservation(row: sqlite3.Row) -> Reservation:
    fee = row["cancellation_fee_mill"]
    return Reservation(
        id=row["id"],
        code=row["code"],
        guest_id=row["guest_id"],
        period=StayPeriod(date_from_db(row["arrival"]), date_from_db(row["departure"])),
        status=ReservationStatus(row["status"]),
        cancellation_fee=None if fee is None else Money(fee),
        notes=row["notes"],
        created_by=row["created_by"],
        created_at=datetime_from_db(row["created_at"]),
        cancelled_at=datetime_from_db(row["cancelled_at"]),
        checked_in_at=datetime_from_db(row["checked_in_at"]),
        checked_out_at=datetime_from_db(row["checked_out_at"]),
        no_show_at=datetime_from_db(row["no_show_at"]),
        version=row["version"],
        guest_name=row["guest_name"],
    )


class ReservationRepository(BaseRepository):
    # ------------------------------------------------------------ reading
    def get(self, reservation_id: int) -> Reservation | None:
        row = self._fetch_one(f"{_SELECT} WHERE r.id = ?", (reservation_id,))
        if row is None:
            return None
        reservation = _to_reservation(row)
        self._load_details([reservation])
        return reservation

    def _load_details(self, reservations: list[Reservation]) -> None:
        if not reservations:
            return
        by_id = {r.id: r for r in reservations}
        # One "?" per id: the ids themselves still travel as parameters.
        marks = ",".join("?" * len(by_id))
        rooms = self._fetch_all(_ROOMS_OF.format(marks=marks), list(by_id))
        for row in rooms:
            by_id[row["reservation_id"]].rooms.append(
                BookedRoom(
                    row["room_id"],
                    row["adults"],
                    row["children"],
                    row["number"],
                    row["category_name"],
                )
            )
        nights = self._fetch_all(_NIGHTS_OF.format(marks=marks), list(by_id))
        for row in nights:
            by_id[row["reservation_id"]].nights.append(
                RoomNight(row["room_id"], date_from_db(row["night"]), Money(row["rate_mill"]))
            )

    def search(self, filters: ReservationFilter, request: PageRequest) -> Page[Reservation]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.query:
            clauses.append("(r.code LIKE ? ESCAPE '\\' OR g.search_name LIKE ? ESCAPE '\\')")
            params += [
                f"%{escape_like(filters.query.upper())}%",
                f"%{escape_like(filters.query.casefold())}%",
            ]
        if filters.status is not None:
            clauses.append("r.status = ?")
            params.append(filters.status.value)
        if filters.arriving_from is not None:
            clauses.append("r.arrival >= ?")
            params.append(date_to_db(filters.arriving_from))
        if filters.arriving_until is not None:
            clauses.append("r.arrival <= ?")
            params.append(date_to_db(filters.arriving_until))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        total = self._fetch_one(_COUNT.format(where=where), params)[0]
        rows = self._fetch_all(
            _PAGE.format(where=where), [*params, request.per_page, request.offset]
        )
        reservations = [_to_reservation(r) for r in rows]
        self._load_details(reservations)
        return Page(reservations, total, request)

    def for_guest(self, guest_id: int) -> list[Reservation]:
        rows = self._fetch_all(
            f"{_SELECT} WHERE r.guest_id = ? ORDER BY r.arrival DESC, r.id DESC",
            (guest_id,),
        )
        reservations = [_to_reservation(r) for r in rows]
        self._load_details(reservations)
        return reservations

    def blocked_nights(
        self, period: StayPeriod, *, exclude_reservation_id: int | None = None
    ) -> dict[int, list[date]]:
        """room_id -> nights of `period` already taken by maintenance or other bookings."""
        # Maintenance nights have no reservation_id: "IS NULL OR <> ?" keeps them.
        rows = self._fetch_all(
            "SELECT room_id, night FROM room_night WHERE night >= ? AND night < ? "
            "AND (reservation_id IS NULL OR reservation_id <> ?) ORDER BY night",
            (date_to_db(period.arrival), date_to_db(period.departure), exclude_reservation_id or 0),
        )
        blocked: dict[int, list[date]] = defaultdict(list)
        for row in rows:
            blocked[row["room_id"]].append(date_from_db(row["night"]))
        return dict(blocked)

    def calendar(self, period: StayPeriod) -> list[BlockedNight]:
        rows = self._fetch_all(
            "SELECT n.room_id, n.night, n.reservation_id, n.maintenance_id, r.status, r.code, "
            "r.arrival, g.first_name || ' ' || g.last_name AS guest_name FROM room_night n "
            "LEFT JOIN reservation r ON r.id = n.reservation_id "
            "LEFT JOIN guest g ON g.id = r.guest_id "
            "WHERE n.night >= ? AND n.night < ?",
            (date_to_db(period.arrival), date_to_db(period.departure)),
        )
        return [
            BlockedNight(
                row["room_id"],
                date_from_db(row["night"]),
                row["reservation_id"],
                row["maintenance_id"],
                row["status"],
                row["code"],
                row["guest_name"],
                date_from_db(row["arrival"]) if row["arrival"] else None,
            )
            for row in rows
        ]

    def _listed(self, where: str, params: tuple, order: str) -> list[Reservation]:
        rows = self._fetch_all(_LISTED.format(select=_SELECT, where=where, order=order), params)
        reservations = [_to_reservation(r) for r in rows]
        self._load_details(reservations)
        return reservations

    def arrivals(self, day: date) -> list[Reservation]:
        """Confirmed stays that should have started by `day` and are not over yet."""
        return self._listed(_WHERE_ARRIVING, (date_to_db(day), date_to_db(day)), _BY_ARRIVAL)

    def departures(self, day: date) -> list[Reservation]:
        """Guests in the house who are due to leave on `day` (or should have left)."""
        return self._listed(_WHERE_LEAVING, (date_to_db(day),), _BY_DEPARTURE)

    def in_house(self) -> list[Reservation]:
        return self._listed(_WHERE_IN_HOUSE, (), _BY_DEPARTURE)

    def in_house_rooms(self) -> dict[int, str]:
        """room_id -> code of the checked-in reservation using it, even on its departure day."""
        rows = self._fetch_all(
            "SELECT rr.room_id, r.code FROM reservation_room rr "
            "JOIN reservation r ON r.id = rr.reservation_id WHERE r.status = 'CHECKED_IN'"
        )
        return {row["room_id"]: row["code"] for row in rows}

    def future_bookings_for_room(self, room_id: int, today: date) -> list[Reservation]:
        """Active reservations that still have nights in this room from today on."""
        sql = _FUTURE_FOR_ROOM.format(select=_SELECT)
        rows = self._fetch_all(sql, (room_id, date_to_db(today)))
        reservations = [_to_reservation(r) for r in rows]
        self._load_details(reservations)
        return reservations

    # ------------------------------------------------------------ writing
    def add(self, reservation: Reservation) -> Reservation:
        cursor = self._execute(
            "INSERT INTO reservation (code, guest_id, arrival, departure, status, notes, "
            "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reservation.code,
                reservation.guest_id,
                date_to_db(reservation.period.arrival),
                date_to_db(reservation.period.departure),
                reservation.status.value,
                reservation.notes,
                reservation.created_by,
                datetime_to_db(reservation.created_at),
            ),
        )
        reservation.id = cursor.lastrowid
        self._insert_rooms_and_nights(reservation)
        return reservation

    def _insert_rooms_and_nights(self, reservation: Reservation) -> None:
        self._conn.executemany(
            "INSERT INTO reservation_room (reservation_id, room_id, adults, children) "
            "VALUES (?, ?, ?, ?)",
            [(reservation.id, r.room_id, r.adults, r.children) for r in reservation.rooms],
        )
        # The (room_id, night) primary key makes a double booking impossible here,
        # even if a check in Python were ever skipped (ADR 0004).
        try:
            self._insert_nights(reservation)
        except sqlite3.IntegrityError as exc:
            raise ConflictError("reservation.night_taken") from exc

    def _insert_nights(self, reservation: Reservation) -> None:
        self._conn.executemany(
            "INSERT INTO room_night (room_id, night, reservation_id, rate_mill) "
            "VALUES (?, ?, ?, ?)",
            [
                (n.room_id, date_to_db(n.night), reservation.id, n.rate.millimes)
                for n in reservation.nights
            ],
        )

    def replace_rooms_and_nights(self, reservation: Reservation) -> None:
        self.release_nights(reservation.id)
        self._execute("DELETE FROM reservation_room WHERE reservation_id = ?", (reservation.id,))
        self._insert_rooms_and_nights(reservation)

    def release_nights(self, reservation_id: int) -> None:
        self._execute("DELETE FROM room_night WHERE reservation_id = ?", (reservation_id,))

    def update(self, reservation: Reservation) -> None:
        fee = reservation.cancellation_fee
        cursor = self._execute(
            "UPDATE reservation SET arrival = ?, departure = ?, status = ?, "
            "cancellation_fee_mill = ?, notes = ?, cancelled_at = ?, checked_in_at = ?, "
            "checked_out_at = ?, no_show_at = ?, version = version + 1 "
            "WHERE id = ? AND version = ?",
            (
                date_to_db(reservation.period.arrival),
                date_to_db(reservation.period.departure),
                reservation.status.value,
                None if fee is None else fee.millimes,
                reservation.notes,
                datetime_to_db(reservation.cancelled_at),
                datetime_to_db(reservation.checked_in_at),
                datetime_to_db(reservation.checked_out_at),
                datetime_to_db(reservation.no_show_at),
                reservation.id,
                reservation.version,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="reservation", id=reservation.id)
        reservation.version += 1


class CounterRepository(BaseRepository):
    def next(self, name: str, year: int) -> int:
        row = self._fetch_one(
            "INSERT INTO counter (name, year, value) VALUES (?, ?, 1) "
            "ON CONFLICT (name, year) DO UPDATE SET value = value + 1 RETURNING value",
            (name, year),
        )
        return row["value"]

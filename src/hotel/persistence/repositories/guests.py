from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime

from hotel.domain.errors import StaleDataError
from hotel.domain.guests import Guest, IdDocType, search_key
from hotel.domain.paging import Page, PageRequest
from hotel.persistence.convert import date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository, escape_like

_SELECT = (
    "SELECT id, first_name, last_name, id_doc_type, id_doc_number, nationality, phone, email, "
    "notes, is_vip, do_not_rent, do_not_rent_reason, is_active, created_at, version, "
    "anonymised_at, archived_at FROM guest"
)

# The only ORDER BY clauses that can ever reach SQL: user input picks a key, never text.
SORT_ORDERS = {
    "name": "sort_name, id",
    "newest": "created_at DESC, id DESC",
    "oldest": "created_at, id",
}
MAX_SEARCH_TERMS = 5

# Written out in full (no concatenation), so every word of the query is visible.
_CANDIDATES = (
    "SELECT id, first_name, last_name, id_doc_type, id_doc_number, nationality, phone, email, "
    "notes, is_vip, do_not_rent, do_not_rent_reason, is_active, created_at, version, "
    "anonymised_at, archived_at FROM guest g WHERE g.anonymised_at IS NULL AND NOT EXISTS ("
    "SELECT 1 FROM reservation r WHERE r.guest_id = g.id "
    "AND r.status IN ('CONFIRMED', 'CHECKED_IN')) "
    "AND COALESCE((SELECT MAX(r.departure) FROM reservation r WHERE r.guest_id = g.id), "
    "substr(g.created_at, 1, 10)) < ? ORDER BY g.sort_name"
)


def _to_guest(row: sqlite3.Row) -> Guest:
    return Guest(
        id=row["id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        id_doc_type=IdDocType(row["id_doc_type"]),
        id_doc_number=row["id_doc_number"],
        nationality=row["nationality"],
        phone=row["phone"],
        email=row["email"],
        notes=row["notes"],
        is_vip=bool(row["is_vip"]),
        do_not_rent=bool(row["do_not_rent"]),
        do_not_rent_reason=row["do_not_rent_reason"],
        is_active=bool(row["is_active"]),
        created_at=datetime_from_db(row["created_at"]),
        version=row["version"],
        anonymised_at=datetime_from_db(row["anonymised_at"]),
        archived_at=datetime_from_db(row["archived_at"]),
    )


def _values(guest: Guest) -> tuple:
    return (
        guest.first_name,
        guest.last_name,
        guest.search_name,
        guest.sort_name,
        guest.id_doc_type.value,
        guest.id_doc_number,
        guest.nationality,
        guest.phone,
        guest.phone_digits,
        guest.email,
        guest.notes,
        int(guest.is_vip),
        int(guest.do_not_rent),
        guest.do_not_rent_reason,
        int(guest.is_active),
    )


class GuestRepository(BaseRepository):
    def get(self, guest_id: int) -> Guest | None:
        row = self._fetch_one(f"{_SELECT} WHERE id = ?", (guest_id,))
        return _to_guest(row) if row else None

    def find_by_document(self, doc_type: IdDocType, number: str) -> Guest | None:
        row = self._fetch_one(
            f"{_SELECT} WHERE id_doc_type = ? AND id_doc_number = ?",
            (doc_type.value, number),
        )
        return _to_guest(row) if row else None

    def probable_duplicates(self, guest: Guest) -> list[Guest]:
        """Same name, and the same phone number or e-mail address."""
        rows = self._fetch_all(
            f"{_SELECT} WHERE search_name = ? AND id IS NOT ? "
            "AND ((phone_digits IS NOT NULL AND phone_digits = ?) "
            "OR (email IS NOT NULL AND email = ?))",
            (guest.search_name, guest.id, guest.phone_digits, guest.email),
        )
        return [_to_guest(r) for r in rows]

    def add(self, guest: Guest) -> Guest:
        cursor = self._execute(
            "INSERT INTO guest (first_name, last_name, search_name, sort_name, id_doc_type, "
            "id_doc_number, nationality, phone, phone_digits, email, notes, is_vip, do_not_rent, "
            "do_not_rent_reason, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*_values(guest), datetime_to_db(guest.created_at)),
        )
        guest.id = cursor.lastrowid
        return guest

    def update(self, guest: Guest) -> None:
        cursor = self._execute(
            "UPDATE guest SET first_name = ?, last_name = ?, search_name = ?, sort_name = ?, "
            "id_doc_type = ?, id_doc_number = ?, nationality = ?, phone = ?, phone_digits = ?, "
            "email = ?, notes = ?, is_vip = ?, do_not_rent = ?, do_not_rent_reason = ?, "
            "is_active = ?, version = version + 1 WHERE id = ? AND version = ?",
            (*_values(guest), guest.id, guest.version),
        )
        if cursor.rowcount != 1:
            raise StaleDataError(entity="guest", id=guest.id)
        guest.version += 1

    def search(
        self, query: str, request: PageRequest, *, sort: str = "name", archived: bool = False
    ) -> Page[Guest]:
        """Every word must match the name, document number, phone or e-mail.

        Values only ever travel as ? parameters, LIKE wildcards typed by the user
        are escaped, and the ORDER BY clause comes from the SORT_ORDERS whitelist.
        Archived guests (story 6.17) are listed only when asked for, and then alone.
        """
        clauses: list[str] = [
            "is_active = 1",
            "archived_at IS NOT NULL" if archived else "archived_at IS NULL",
        ]
        params: list[object] = []
        for term in query.split()[:MAX_SEARCH_TERMS]:
            options = ["search_name LIKE ? ESCAPE '\\'", "email LIKE ? ESCAPE '\\'"]
            params += [f"%{escape_like(search_key(term))}%", f"%{escape_like(term.lower())}%"]
            document = re.sub(r"[\s\-./]", "", term).upper()
            if len(document) >= 3:
                options.append("id_doc_number LIKE ? ESCAPE '\\'")
                params.append(f"{escape_like(document)}%")
            digits = re.sub(r"\D", "", term)
            if len(digits) >= 3:
                options.append("phone_digits LIKE ? ESCAPE '\\'")
                params.append(f"%{digits}%")
            clauses.append("(" + " OR ".join(options) + ")")
        where = " WHERE " + " AND ".join(clauses)
        order = SORT_ORDERS.get(sort, SORT_ORDERS["name"])
        count_sql = f"SELECT COUNT(*) FROM guest{where}"  # noqa: S608  # nosec B608
        total = self._fetch_one(count_sql, params)[0]
        page_sql = f"{_SELECT}{where} ORDER BY {order} LIMIT ? OFFSET ?"  # nosec B608
        rows = self._fetch_all(page_sql, [*params, request.per_page, request.offset])
        return Page([_to_guest(r) for r in rows], total, request)

    # ------------------------------------------------------------ anonymisation (5.7)
    def anonymisation_candidates(self, cutoff: date) -> list[Guest]:
        """Not anonymised yet, no current or future stay, nothing since `cutoff`.

        "Nothing since" is the last departure, or the registration date for a
        guest who never stayed.
        """
        rows = self._fetch_all(_CANDIDATES, (date_to_db(cutoff),))
        return [_to_guest(r) for r in rows]

    def mark_anonymised(self, guest: Guest) -> None:
        self._execute(
            "UPDATE guest SET anonymised_at = ? WHERE id = ?",
            (datetime_to_db(guest.anonymised_at), guest.id),
        )
        # Booking notes can hold personal details too ("allergic to feathers").
        self._execute("UPDATE reservation SET notes = '' WHERE guest_id = ?", (guest.id,))

    # ------------------------------------------------------------ delete or archive (6.17)
    def count_stays(self, guest_id: int) -> tuple[int, int]:
        """(every reservation of the guest, those still running or to come)."""
        row = self._fetch_one(
            "SELECT COUNT(*), COALESCE(SUM(status IN ('CONFIRMED', 'CHECKED_IN')), 0) "
            "FROM reservation WHERE guest_id = ?",
            (guest_id,),
        )
        return row[0], row[1]

    def count_archived(self) -> int:
        return self._fetch_one("SELECT COUNT(*) FROM guest WHERE archived_at IS NOT NULL")[0]

    def archive(self, guest_id: int, now: datetime | None) -> None:
        """`now` archives, None restores; the version changes so open forms go stale."""
        self._execute(
            "UPDATE guest SET archived_at = ?, version = version + 1 WHERE id = ?",
            (datetime_to_db(now), guest_id),
        )

    def delete(self, guest_id: int) -> None:
        self._execute("DELETE FROM guest WHERE id = ?", (guest_id,))

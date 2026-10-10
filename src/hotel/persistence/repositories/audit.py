from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime

from hotel.domain.audit import GENESIS_HASH, AuditEntry, chain_hash
from hotel.domain.paging import Page, PageRequest
from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository, escape_like

_SELECT = (
    "SELECT id, at, user_id, username, action, entity, entity_id, details, ip, prev_hash, hash "
    "FROM audit_log"
)


_UNREADABLE = datetime(1970, 1, 1, tzinfo=UTC)


def _read_time(value: str) -> datetime:
    # A row edited by hand may hold anything; it must still be checkable (and
    # fail the hash check) instead of crashing the verification.
    try:
        return datetime_from_db(value)
    except (TypeError, ValueError):
        return _UNREADABLE


def _to_entry(row: sqlite3.Row) -> AuditEntry:
    return AuditEntry(
        id=row["id"],
        at=_read_time(row["at"]),
        user_id=row["user_id"],
        username=row["username"],
        action=row["action"],
        entity=row["entity"],
        entity_id=row["entity_id"],
        details=json.loads(row["details"]),
        ip=row["ip"],
        prev_hash=row["prev_hash"],
        hash=row["hash"],
    )


class AuditRepository(BaseRepository):
    def latest_hash(self) -> str:
        row = self._fetch_one("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1")
        return row["hash"] if row else GENESIS_HASH

    def append(self, entry: AuditEntry) -> AuditEntry:
        # Safe without extra locking: the Unit of Work holds the write lock
        # (BEGIN IMMEDIATE), so no other entry can be added between these lines.
        previous = self.latest_hash()
        chained = replace(entry, prev_hash=previous, hash=chain_hash(previous, entry))
        cursor = self._execute(
            "INSERT INTO audit_log (at, user_id, username, action, entity, entity_id, details, "
            "ip, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime_to_db(chained.at),
                chained.user_id,
                chained.username,
                chained.action,
                chained.entity,
                chained.entity_id,
                json.dumps(dict(chained.details), sort_keys=True, ensure_ascii=False),
                chained.ip,
                chained.prev_hash,
                chained.hash,
            ),
        )
        return replace(chained, id=cursor.lastrowid)

    def iterate(self) -> Iterator[AuditEntry]:
        for row in self._conn.execute(f"{_SELECT} ORDER BY id"):
            yield _to_entry(row)

    def search(
        self,
        request: PageRequest,
        *,
        user_id: int | None = None,
        action_prefix: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Page[AuditEntry]:
        clauses, params = [], []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if action_prefix:
            clauses.append("action LIKE ? ESCAPE '\\'")
            params.append(escape_like(action_prefix) + "%")
        if since is not None:
            clauses.append("at >= ?")
            params.append(datetime_to_db(since))
        if until is not None:
            clauses.append("at < ?")
            params.append(datetime_to_db(until))
        # Only fixed SQL fragments are joined; every value is a ? parameter.
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        count_sql = f"SELECT COUNT(*) FROM audit_log{where}"  # noqa: S608  # nosec B608
        total = self._fetch_one(count_sql, params)[0]
        rows = self._fetch_all(
            f"{_SELECT}{where} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, request.per_page, request.offset],
        )
        return Page([_to_entry(r) for r in rows], total, request)

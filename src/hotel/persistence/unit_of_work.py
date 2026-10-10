"""Unit of Work: one database transaction per business operation.

    with uow_factory() as uow:
        user = uow.users.get_by_username("amira")
        ...
        uow.users.update(user)

Leaving the `with` block normally commits everything; leaving it because of
an exception rolls everything back. A business operation therefore either
happens completely or not at all, even if it touches several tables.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from types import TracebackType

from hotel.persistence.db import connect
from hotel.persistence.repositories.audit import AuditRepository
from hotel.persistence.repositories.login_failures import LoginFailureRepository
from hotel.persistence.repositories.sessions import SessionRepository
from hotel.persistence.repositories.users import UserRepository


class UnitOfWork:
    audit: AuditRepository
    users: UserRepository
    sessions: SessionRepository
    login_failures: LoginFailureRepository

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> UnitOfWork:
        self._conn = connect(self._database_path)
        # IMMEDIATE takes the write lock now rather than at the first write, so two
        # operations can never both read "room is free" and then both write.
        self._conn.execute("BEGIN IMMEDIATE")
        self.audit = AuditRepository(self._conn)
        self.users = UserRepository(self._conn)
        self.sessions = SessionRepository(self._conn)
        self.login_failures = LoginFailureRepository(self._conn)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._conn is None:
            raise RuntimeError("UnitOfWork.__exit__ called without __enter__")
        try:
            self._conn.execute("COMMIT" if exc_type is None else "ROLLBACK")
        finally:
            self._conn.close()
            self._conn = None


UnitOfWorkFactory = Callable[[], UnitOfWork]

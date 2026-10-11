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
from hotel.persistence.repositories.billing import DiscountRepository, PaymentRepository
from hotel.persistence.repositories.extras import ExtraRepository, ServiceChargeRepository
from hotel.persistence.repositories.form_tokens import FormTokenRepository
from hotel.persistence.repositories.guests import GuestRepository
from hotel.persistence.repositories.invoices import InvoiceRepository
from hotel.persistence.repositories.login_failures import LoginFailureRepository
from hotel.persistence.repositories.night_audit import SnapshotRepository
from hotel.persistence.repositories.reports import ReportRepository
from hotel.persistence.repositories.reservations import CounterRepository, ReservationRepository
from hotel.persistence.repositories.rooms import (
    CategoryRepository,
    MaintenanceRepository,
    RoomRepository,
)
from hotel.persistence.repositories.sessions import SessionRepository
from hotel.persistence.repositories.settings import SettingRepository
from hotel.persistence.repositories.taxes import TaxRuleRepository
from hotel.persistence.repositories.users import UserRepository


class UnitOfWork:
    audit: AuditRepository
    users: UserRepository
    sessions: SessionRepository
    login_failures: LoginFailureRepository
    categories: CategoryRepository
    rooms: RoomRepository
    maintenance: MaintenanceRepository
    guests: GuestRepository
    settings: SettingRepository
    reservations: ReservationRepository
    counters: CounterRepository
    form_tokens: FormTokenRepository
    extras: ExtraRepository
    charges: ServiceChargeRepository
    tax_rules: TaxRuleRepository
    discounts: DiscountRepository
    payments: PaymentRepository
    invoices: InvoiceRepository
    reports: ReportRepository
    snapshots: SnapshotRepository

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
        self.categories = CategoryRepository(self._conn)
        self.rooms = RoomRepository(self._conn)
        self.maintenance = MaintenanceRepository(self._conn)
        self.guests = GuestRepository(self._conn)
        self.settings = SettingRepository(self._conn)
        self.reservations = ReservationRepository(self._conn)
        self.counters = CounterRepository(self._conn)
        self.form_tokens = FormTokenRepository(self._conn)
        self.extras = ExtraRepository(self._conn)
        self.charges = ServiceChargeRepository(self._conn)
        self.tax_rules = TaxRuleRepository(self._conn)
        self.discounts = DiscountRepository(self._conn)
        self.payments = PaymentRepository(self._conn)
        self.invoices = InvoiceRepository(self._conn)
        self.reports = ReportRepository(self._conn)
        self.snapshots = SnapshotRepository(self._conn)
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

"""Composition root: the one place where all the parts are connected.

Both the web application and the command line call build_services(), which
is how the business logic stays independent of the web layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib import resources

from hotel.config import Settings
from hotel.domain.clock import Clock, SystemClock
from hotel.domain.passwords import PasswordPolicy
from hotel.persistence.backup import create_backup
from hotel.persistence.db import initialise_database
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import AuditService
from hotel.services.auth import AuthService
from hotel.services.backups import BackupService
from hotel.services.billing import BillingService
from hotel.services.extras import ExtrasService
from hotel.services.form_tokens import FormTokenService
from hotel.services.front_desk import FrontDeskService
from hotel.services.guests import GuestService
from hotel.services.hotel_settings import HotelSettingsService
from hotel.services.invoices import InvoiceService
from hotel.services.night_audit import NightAuditService
from hotel.services.passwords import PasswordHasher, ScryptParams
from hotel.services.reports import ReportService
from hotel.services.reservations import ReservationService
from hotel.services.rooms import RoomService
from hotel.services.two_factor import TwoFactorService
from hotel.services.users import UserService


@cache
def load_common_passwords() -> frozenset[str]:
    text = resources.files("hotel.data").joinpath("common_passwords.txt").read_text("utf-8")
    return frozenset(line.strip().casefold() for line in text.splitlines() if line.strip())


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    clock: Clock
    uow_factory: UnitOfWorkFactory
    schema_version: int
    auth: AuthService
    audit: AuditService
    users: UserService
    rooms: RoomService
    guests: GuestService
    backups: BackupService
    reservations: ReservationService
    form_tokens: FormTokenService
    front_desk: FrontDeskService
    extras: ExtrasService
    hotel_settings: HotelSettingsService
    billing: BillingService
    invoices: InvoiceService
    reports: ReportService
    night_audit: NightAuditService
    two_factor: TwoFactorService

    def is_healthy(self) -> bool:
        """True when the database answers (used by the /health page)."""
        try:
            with self.uow_factory() as uow:
                uow.users.count()
        except Exception:  # any failure means "not healthy"; the caller logs it
            return False
        return True


def build_services(settings: Settings, *, clock: Clock | None = None) -> Services:
    clock = clock or SystemClock(settings.tz)

    def backup_before_upgrade(current_version: int) -> None:
        # A failed or unwanted upgrade can always be undone from this copy.
        create_backup(
            settings.database_path,
            settings.backup_dir,
            clock.local_now(),
            label=f"pre-upgrade-v{current_version}",
        )

    schema_version = initialise_database(
        settings.database_path, before_upgrade=backup_before_upgrade
    )

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(settings.database_path)

    hasher = PasswordHasher(ScryptParams(n=settings.scrypt_n))
    policy = PasswordPolicy(common_passwords=load_common_passwords())
    reservations = ReservationService(uow_factory, clock)
    reports = ReportService(uow_factory, clock)
    return Services(
        settings=settings,
        clock=clock,
        uow_factory=uow_factory,
        schema_version=schema_version,
        auth=AuthService(uow_factory, clock, hasher, policy),
        audit=AuditService(uow_factory, clock),
        users=UserService(uow_factory, clock, hasher, policy),
        rooms=RoomService(uow_factory, clock),
        guests=GuestService(uow_factory, clock),
        backups=BackupService(uow_factory, clock, settings.database_path, settings.backup_dir),
        reservations=reservations,
        form_tokens=FormTokenService(uow_factory, clock),
        front_desk=FrontDeskService(uow_factory, clock),
        extras=ExtrasService(uow_factory, clock),
        hotel_settings=HotelSettingsService(uow_factory, clock),
        billing=BillingService(uow_factory, clock),
        invoices=InvoiceService(uow_factory, clock),
        reports=reports,
        night_audit=NightAuditService(uow_factory, clock, reservations, reports),
        two_factor=TwoFactorService(uow_factory, clock),
    )

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
from hotel.persistence.db import initialise_database
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.auth import AuthService
from hotel.services.passwords import PasswordHasher, ScryptParams


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


def build_services(settings: Settings, *, clock: Clock | None = None) -> Services:
    schema_version = initialise_database(settings.database_path)
    clock = clock or SystemClock(settings.tz)

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(settings.database_path)

    hasher = PasswordHasher(ScryptParams(n=settings.scrypt_n))
    policy = PasswordPolicy(common_passwords=load_common_passwords())
    return Services(
        settings=settings,
        clock=clock,
        uow_factory=uow_factory,
        schema_version=schema_version,
        auth=AuthService(uow_factory, clock, hasher, policy),
    )

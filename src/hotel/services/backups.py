"""Backups: manual, automatic (daily, rotated) and restore."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import PermissionDeniedError
from hotel.persistence.backup import (
    BackupFile,
    create_backup,
    list_backups,
    restore_backup,
    rotate,
)
from hotel.persistence.unit_of_work import UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role

AUTO_LABEL = "auto"
KEEP_AUTOMATIC = 14  # two weeks of daily backups
AUTO_INTERVAL = timedelta(hours=24)


class BackupService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, database_path: Path, backup_dir: Path
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._database_path = database_path
        self.backup_dir = backup_dir

    def list(self, actor: Actor) -> list[BackupFile]:
        require_role(actor, Role.MANAGER)
        return list_backups(self.backup_dir)

    def create(self, actor: Actor, *, label: str = "manual") -> Path:
        require_role(actor, Role.MANAGER)
        path = create_backup(
            self._database_path, self.backup_dir, self._clock.local_now(), label=label
        )
        with self._uow() as uow:
            record(uow, self._clock, actor, "backup.created", file=path.name)
        return path

    def auto_backup_if_due(self) -> Path | None:
        """Take the daily backup if the last automatic one is older than 24 hours."""
        latest = next((b for b in list_backups(self.backup_dir) if b.label == AUTO_LABEL), None)
        now = self._clock.local_now().replace(tzinfo=None)
        if latest is not None and now - latest.created_at < AUTO_INTERVAL:
            return None
        path = self.create(Actor.system("scheduler"), label=AUTO_LABEL)
        rotate(self.backup_dir, label=AUTO_LABEL, keep=KEEP_AUTOMATIC)
        return path

    def restore(self, actor: Actor, backup: Path) -> Path:
        """Command line only, with the application stopped."""
        if not actor.is_system:
            raise PermissionDeniedError(required="command line")
        safety_copy = restore_backup(
            self._database_path, backup, self.backup_dir, self._clock.local_now()
        )
        with self._uow() as uow:
            record(
                uow,
                self._clock,
                actor,
                "backup.restored",
                file=backup.name,
                safety_copy=safety_copy.name,
            )
        return safety_copy

import sqlite3
from datetime import datetime, timedelta

import pytest

from hotel.bootstrap import build_services
from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from hotel.domain.errors import PermissionDeniedError
from hotel.domain.users import User
from hotel.persistence.backup import (
    BackupError,
    create_backup,
    list_backups,
    restore_backup,
    rotate,
)
from hotel.persistence.db import connect
from hotel.persistence.migrate import discover_migrations, migrate
from tests.conftest import MANAGER_PASSWORD

NOW = datetime(2026, 7, 8, 13, 0)  # noqa: DTZ001 - local hotel time, as used in file names


def _guest_count(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM app_user").fetchone()[0]
    finally:
        conn.close()


def test_backup_is_a_consistent_verified_copy(settings, manager):
    path = create_backup(settings.database_path, settings.backup_dir, NOW)
    assert path.name == "hotel-20260708-130000-manual.db"
    assert _guest_count(path) == 1
    assert not list(settings.backup_dir.glob("*.partial"))
    second = create_backup(settings.database_path, settings.backup_dir, NOW)
    assert second.name == "hotel-20260708-130000-manual-1.db"  # never overwrites
    names = {b.name for b in list_backups(settings.backup_dir)}
    assert names == {"hotel-20260708-130000-manual-1.db", "hotel-20260708-130000-manual.db"}


def test_list_ignores_unrelated_files(settings, tmp_path):
    assert list_backups(tmp_path / "missing") == []
    settings.backup_dir.mkdir()
    (settings.backup_dir / "notes.txt").write_text("x")
    assert list_backups(settings.backup_dir) == []


def test_rotation_keeps_the_newest_of_one_kind(settings, manager):
    for day in range(5):
        create_backup(
            settings.database_path, settings.backup_dir, NOW + timedelta(days=day), label="auto"
        )
    create_backup(settings.database_path, settings.backup_dir, NOW, label="manual")
    removed = rotate(settings.backup_dir, label="auto", keep=3)
    assert [p.name for p in removed] == [
        "hotel-20260709-130000-auto.db",
        "hotel-20260708-130000-auto.db",
    ]
    labels = [b.label for b in list_backups(settings.backup_dir)]
    assert labels.count("auto") == 3
    assert labels.count("manual") == 1


def test_restore_brings_back_old_data_and_keeps_a_safety_copy(services, settings, manager):
    backup = create_backup(settings.database_path, settings.backup_dir, NOW)
    services.users.create_user(
        Actor(manager),
        username="rita",
        full_name="Rita",
        role=Role.RECEPTIONIST,
        temporary_password=MANAGER_PASSWORD,
    )
    assert _guest_count(settings.database_path) == 2
    safety = restore_backup(
        settings.database_path, backup, settings.backup_dir, NOW + timedelta(hours=1)
    )
    assert _guest_count(settings.database_path) == 1
    assert _guest_count(safety) == 2
    assert safety.name.endswith("-pre-restore.db")


def test_restore_refuses_broken_or_newer_files(settings, manager, tmp_path):
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"not a database at all" * 100)
    with pytest.raises(BackupError, match="not a valid database"):
        restore_backup(settings.database_path, broken, settings.backup_dir, NOW)
    with pytest.raises(BackupError, match="does not exist"):
        restore_backup(settings.database_path, tmp_path / "nope.db", settings.backup_dir, NOW)
    future = create_backup(settings.database_path, settings.backup_dir, NOW)
    conn = sqlite3.connect(future)
    conn.execute("PRAGMA user_version = 999")
    conn.close()
    with pytest.raises(BackupError, match="newer version"):
        restore_backup(settings.database_path, future, settings.backup_dir, NOW)


def test_service_audits_and_restricts(services, manager):
    boss = Actor(manager)
    path = services.backups.create(boss)
    assert [b.path for b in services.backups.list(boss)] == [path]
    with services.uow_factory() as uow:
        assert list(uow.audit.iterate())[-1].action == "backup.created"
    rita = Actor(User(manager.id, "x", "X", "x", Role.RECEPTIONIST))
    with pytest.raises(PermissionDeniedError):
        services.backups.create(rita)
    with pytest.raises(PermissionDeniedError):
        services.backups.restore(boss, path)  # command line only
    services.backups.restore(Actor.system(), path)
    with services.uow_factory() as uow:
        assert list(uow.audit.iterate())[-1].action == "backup.restored"


def test_automatic_backup_runs_once_a_day(services, clock, manager):
    first = services.backups.auto_backup_if_due()
    assert first is not None
    assert services.backups.auto_backup_if_due() is None
    clock.advance(timedelta(hours=23))
    assert services.backups.auto_backup_if_due() is None
    clock.advance(timedelta(hours=1))
    assert services.backups.auto_backup_if_due() is not None
    for _ in range(20):
        clock.advance(timedelta(days=1))
        services.backups.auto_backup_if_due()
    autos = [b for b in services.backups.list(Actor.system()) if b.label == "auto"]
    assert len(autos) == 14


def test_an_upgrade_is_preceded_by_a_backup(settings, clock):
    conn = connect(settings.database_path)
    migrate(conn, discover_migrations()[:1])  # a database from Sprint 1
    conn.close()
    build_services(settings, clock=clock)
    names = [b.name for b in list_backups(settings.backup_dir)]
    assert names == ["hotel-20260708-130000-pre-upgrade-v1.db"]
    build_services(settings, clock=clock)  # already up to date: no new backup
    assert len(list_backups(settings.backup_dir)) == 1

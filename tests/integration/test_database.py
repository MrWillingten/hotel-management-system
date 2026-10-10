import sqlite3
from datetime import UTC, datetime

import pytest

from hotel.domain.enums import Role
from hotel.domain.errors import StaleDataError
from hotel.domain.users import User
from hotel.persistence.convert import date_from_db, date_to_db, datetime_from_db, datetime_to_db
from hotel.persistence.db import (
    DatabaseUnavailableError,
    check_sqlite_version,
    connect,
    initialise_database,
    quick_check,
)
from hotel.persistence.migrate import Migration, MigrationError, discover_migrations, migrate
from hotel.persistence.unit_of_work import UnitOfWork


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "hotel.db"
    initialise_database(path)
    return path


def _user(username="amira"):
    return User(
        id=None,
        username=username,
        full_name="Amira",
        password_hash="scrypt$x",
        role=Role.RECEPTIONIST,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
    )


def test_every_connection_enforces_foreign_keys(db_path):
    conn = connect(db_path)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO user_session VALUES (?, 999, 'x', 'x', 'x', NULL, NULL)", ("a" * 64,)
        )
    conn.close()


def test_database_uses_wal_and_passes_integrity_check(db_path):
    conn = connect(db_path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert quick_check(conn)
    conn.close()


def test_initialise_is_idempotent(db_path):
    assert initialise_database(db_path) == len(discover_migrations())


def test_old_sqlite_is_refused():
    with pytest.raises(DatabaseUnavailableError, match=r"3\.35\.0"):
        check_sqlite_version((3, 34, 1))
    check_sqlite_version((3, 46, 0))


def test_corrupted_database_is_refused(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    with pytest.raises((DatabaseUnavailableError, sqlite3.DatabaseError)):
        initialise_database(path)


def test_failed_migration_leaves_the_schema_untouched(tmp_path):
    conn = connect(tmp_path / "m.db")
    good = Migration(1, "0001_good.sql", "CREATE TABLE a (x INTEGER);")
    bad = Migration(2, "0002_bad.sql", "CREATE TABLE b (x INTEGER); THIS IS NOT SQL;")
    with pytest.raises(MigrationError, match=r"0002_bad\.sql"):
        migrate(conn, [good, bad])
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"a"}  # table b was rolled back with its migration
    conn.close()


def test_database_newer_than_program_is_refused(tmp_path):
    conn = connect(tmp_path / "m.db")
    conn.execute("PRAGMA user_version = 99")
    with pytest.raises(MigrationError, match="newer"):
        migrate(conn, [Migration(1, "0001_a.sql", "SELECT 1;")])
    conn.close()


def test_unit_of_work_commits_on_success(db_path):
    with UnitOfWork(db_path) as uow:
        uow.users.add(_user())
    with UnitOfWork(db_path) as uow:
        assert uow.users.get_by_username("amira") is not None


def test_unit_of_work_rolls_back_everything_on_error(db_path):
    """A failure halfway through an operation must leave no partial data behind."""

    def operation_that_crashes_halfway():
        with UnitOfWork(db_path) as uow:
            uow.users.add(_user("first"))
            uow.users.add(_user("second"))
            raise RuntimeError("simulated crash in the middle of an operation")

    with pytest.raises(RuntimeError):
        operation_that_crashes_halfway()
    with UnitOfWork(db_path) as uow:
        assert uow.users.count() == 0


def test_optimistic_locking_rejects_a_stale_update(db_path):
    with UnitOfWork(db_path) as uow:
        user_id = uow.users.add(_user()).id
    with UnitOfWork(db_path) as uow:
        first_copy = uow.users.get(user_id)
    with UnitOfWork(db_path) as uow:
        second_copy = uow.users.get(user_id)
        second_copy.full_name = "Amira B."
        uow.users.update(second_copy)
    first_copy.full_name = "Someone else's edit"
    with pytest.raises(StaleDataError), UnitOfWork(db_path) as uow:
        uow.users.update(first_copy)
    with UnitOfWork(db_path) as uow:
        assert uow.users.get(user_id).full_name == "Amira B."


def test_datetime_conversion_keeps_sortable_text():
    whole = datetime(2026, 7, 8, 12, 0, 5, tzinfo=UTC)
    fractional = datetime(2026, 7, 8, 12, 0, 5, 1, tzinfo=UTC)
    assert datetime_to_db(whole) < datetime_to_db(fractional)
    assert datetime_from_db(datetime_to_db(whole)) == whole
    assert datetime_to_db(None) is None
    assert datetime_from_db(None) is None
    with pytest.raises(ValueError, match="naive"):
        datetime_to_db(datetime(2026, 7, 8))  # noqa: DTZ001
    assert date_from_db(date_to_db(whole.date())) == whole.date()

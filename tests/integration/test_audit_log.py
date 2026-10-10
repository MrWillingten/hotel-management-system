import sqlite3
from datetime import date, timedelta

import pytest

from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from hotel.domain.errors import AuthenticationError, PermissionDeniedError
from hotel.domain.paging import PageRequest
from hotel.domain.users import User
from hotel.persistence.db import connect
from hotel.services.audit import AuditFilter, record
from tests.conftest import MANAGER_PASSWORD


def _actions(services):
    with services.uow_factory() as uow:
        return [e.action for e in uow.audit.iterate()]


def test_creating_the_first_manager_is_audited(services, manager):
    assert _actions(services) == ["user.created"]


def test_sign_in_events_are_audited(services, manager):
    with pytest.raises(AuthenticationError):
        services.auth.login("mona", "wrong password!", ip="10.0.0.1")
    with pytest.raises(AuthenticationError):
        services.auth.login("ghost", "my-actual-password", ip="10.0.0.1")
    token = services.auth.login("mona", MANAGER_PASSWORD, ip="10.0.0.1").token
    services.auth.logout(token)
    assert _actions(services) == [
        "user.created",
        "auth.login_failed",
        "auth.login_failed",
        "auth.login",
        "auth.logout",
    ]
    with services.uow_factory() as uow:
        unknown = list(uow.audit.iterate())[2]
    # Attempted names of unknown accounts are not stored (they may be passwords).
    assert unknown.username == "anonymous"
    assert "my-actual-password" not in unknown.canonical()
    assert "ghost" not in unknown.canonical()


def test_lockout_is_audited(services, manager):
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            services.auth.login("mona", "wrong password!", ip="10.0.0.1")
    assert _actions(services)[-1] == "auth.account_locked"


def test_throttling_is_audited(services, manager):
    for _ in range(21):
        with pytest.raises(AuthenticationError):
            services.auth.login("ghost", "x" * 12, ip="10.9.9.9")
    assert _actions(services)[-1] == "auth.throttled"


def test_audit_entries_roll_back_with_their_operation(services, manager):
    def failing_operation():
        with services.uow_factory() as uow:
            record(uow, services.clock, Actor.system(), "room.created", entity="room", entity_id=1)
            raise RuntimeError("crash after writing the audit entry")

    with pytest.raises(RuntimeError):
        failing_operation()
    assert _actions(services) == ["user.created"]


def test_database_refuses_updates_and_deletes(settings, manager):
    conn = connect(settings.database_path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET action = 'x.y'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_log")
    conn.close()


def test_verify_detects_tampering_done_outside_the_application(services, settings, manager):
    manager_actor = Actor(manager)
    services.auth.logout(services.auth.login("mona", MANAGER_PASSWORD, ip="1.2.3.4").token)
    assert services.audit.verify(manager_actor).ok

    # An attacker with the database file drops the trigger and rewrites history.
    conn = connect(settings.database_path)
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET ip = '8.8.8.8' WHERE id = 2")
    conn.close()

    check = services.audit.verify(manager_actor)
    assert (check.ok, check.broken_at, check.reason) == (False, 2, "content")


def test_search_filters_and_pages(services, clock, manager):
    for _ in range(3):
        services.auth.logout(services.auth.login("mona", MANAGER_PASSWORD, ip="1.2.3.4").token)
        clock.advance(timedelta(days=1))
    actor = Actor(manager)
    everything = services.audit.search(actor, AuditFilter(), PageRequest(per_page=4))
    assert everything.total == 7
    assert everything.pages == 2
    assert everything.items[0].id == 7  # newest first
    logins = services.audit.search(actor, AuditFilter(action_prefix="auth."), PageRequest())
    assert logins.total == 6
    first_day = services.audit.search(
        actor, AuditFilter(since=date(2026, 7, 8), until=date(2026, 7, 8)), PageRequest()
    )
    assert first_day.total == 3
    by_user = services.audit.search(actor, AuditFilter(user_id=manager.id), PageRequest())
    assert by_user.total == 6
    wildcard = services.audit.search(actor, AuditFilter(action_prefix="%"), PageRequest())
    assert wildcard.total == 0  # LIKE wildcards are escaped
    assert services.audit.known_users(actor) == [(manager.id, "mona")]


def test_only_managers_can_read_the_log(services, manager):
    receptionist = User(1, "rita", "Rita", "x", Role.RECEPTIONIST)
    with pytest.raises(PermissionDeniedError):
        services.audit.verify(Actor(receptionist))
    with pytest.raises(PermissionDeniedError):
        services.audit.search(Actor(receptionist), AuditFilter(), PageRequest())

"""Shared test fixtures.

Every test gets its own empty database in a temporary folder, a fixed clock
(8 July 2026, 12:00 UTC) and a deliberately cheap password hash so the suite
stays fast. CSRF protection stays ON in tests: they go through the same
checks as a real browser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from hotel.bootstrap import build_services
from hotel.config import Settings
from hotel.domain.clock import FixedClock
from hotel.web import create_app

TUNIS = ZoneInfo("Africa/Tunis")
MANAGER_PASSWORD = "cognac-and-cedar-2026"
_CSRF_FIELD = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def settings(tmp_path):
    return Settings(environment="testing", data_dir=tmp_path, scrypt_n=2**10)


@pytest.fixture
def clock():
    return FixedClock(datetime(2026, 7, 8, 12, 0, tzinfo=UTC), TUNIS)


@pytest.fixture
def services(settings, clock):
    return build_services(settings, clock=clock)


@pytest.fixture
def manager(services):
    return services.auth.create_first_manager("mona", "Mona Ben Salah", MANAGER_PASSWORD)


@pytest.fixture
def app(settings, services):
    return create_app(settings, services=services)


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(client, path: str = "/login") -> str:
    match = _CSRF_FIELD.search(client.get(path, follow_redirects=True).get_data(as_text=True))
    assert match, f"no CSRF token on {path}"
    return match.group(1)


def login(client, username: str = "mona", password: str = MANAGER_PASSWORD, **extra):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": csrf_token(client),
            **extra,
        },
    )


@pytest.fixture
def signed_in(client, manager):
    response = login(client)
    assert response.status_code == 302
    return client


# ---------------------------------------------------------------- a small hotel
@dataclass
class SmallHotel:
    """Deluxe 204 (2 guests, 180 DT), Deluxe 205 (2, 180), Standard 101 (2, 120),
    Suite 401 (4, 320), a receptionist and two guests."""

    boss: object
    rita: object
    rooms: dict
    amira: object
    karim: object


@pytest.fixture
def hotel(services, manager):
    from hotel.domain.actor import Actor
    from hotel.domain.enums import Role
    from hotel.domain.guests import GuestDetails
    from hotel.domain.money import Money

    boss = Actor(manager)
    rita_user = services.users.create_user(
        boss,
        username="rita",
        full_name="Rita",
        role=Role.RECEPTIONIST,
        temporary_password=MANAGER_PASSWORD,
    )
    rooms = {}
    for name, capacity, rate, numbers in (
        ("Deluxe", 2, 180, ["204", "205"]),
        ("Standard", 2, 120, ["101"]),
        ("Suite", 4, 320, ["401"]),
    ):
        category = services.rooms.create_category(boss, name=name)
        for number in numbers:
            rooms[number] = services.rooms.create_room(
                boss,
                number=number,
                category_id=category.id,
                capacity=capacity,
                nightly_rate=Money.from_dinars(rate),
            )
    amira = services.guests.register(
        boss, GuestDetails("Amira", "Ben Salah", "CIN", "09123456", phone="+216 20 123 456")
    )
    karim = services.guests.register(boss, GuestDetails("Karim", "Haddad", "CIN", "11112222"))
    return SmallHotel(boss, Actor(rita_user), rooms, amira, karim)

"""The read-only JSON API and its tokens, through HTTP (story 6.3)."""

from datetime import date, timedelta

import pytest

from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest
from tests.conftest import csrf_token, login


@pytest.fixture
def token(services, hotel):
    return services.api_tokens.create(hotel.boss, name="dashboard", days=30).secret


@pytest.fixture
def booking(services, hotel):
    return services.reservations.create(
        hotel.boss,
        guest_id=hotel.amira.id,
        period=StayPeriod(date(2026, 7, 10), date(2026, 7, 13)),
        rooms=[RoomRequest(hotel.rooms["204"].id, 2)],
    )


def _get(client, path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(path, headers=headers)


# ------------------------------------------------------------ authentication
def test_the_api_needs_a_token(client, hotel):
    response = _get(client, "/api/v1/rooms")
    assert response.status_code == 401
    assert response.get_json() == {"error": "unauthorized"}
    assert response.headers["WWW-Authenticate"] == 'Bearer realm="hotel"'
    assert _get(client, "/api/v1/rooms", "hotel_wrong").status_code == 401
    bad_scheme = client.get("/api/v1/rooms", headers={"Authorization": "Basic abc"})
    assert bad_scheme.status_code == 401


def test_a_browser_session_is_not_enough(signed_in, hotel):
    """A signed-in browser cannot be tricked into calling the API (no cookie auth)."""
    assert signed_in.get("/api/v1/rooms").status_code == 401


def test_the_api_is_read_only(client, token):
    response = client.post("/api/v1/rooms", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 405


def test_wrong_tokens_from_one_address_are_slowed_down(client, hotel):
    codes = [_get(client, "/api/v1/rooms", "hotel_guess").status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_calls_are_rate_limited_per_manager(client, token, clock):
    for _ in range(120):
        assert _get(client, "/api/v1/", token).status_code == 200
    limited = _get(client, "/api/v1/", token)
    assert limited.status_code == 429
    assert limited.get_json() == {"error": "too_many_requests"}
    assert int(limited.headers["Retry-After"]) > 0
    clock.advance(timedelta(minutes=1))
    assert _get(client, "/api/v1/", token).status_code == 200


# ------------------------------------------------------------ data
def test_index_lists_the_endpoints(client, token):
    data = _get(client, "/api/v1/", token).get_json()
    assert data["version"] == 1
    assert "/api/v1/rooms" in data["endpoints"]


def test_rooms(client, token, booking):
    rooms = {r["number"]: r for r in _get(client, "/api/v1/rooms", token).get_json()["rooms"]}
    assert rooms["204"]["nightly_rate_millimes"] == 180_000
    assert rooms["204"]["category"] == "Deluxe"
    assert rooms["101"]["tonight"] == "AVAILABLE"


def test_availability(client, token, booking):
    data = _get(
        client, "/api/v1/availability?arrival=2026-07-11&departure=2026-07-12&guests=2", token
    ).get_json()
    assert {r["number"] for r in data["rooms"]} == {"205", "101", "401"}  # 204 is booked
    assert data["arrival"] == "2026-07-11"


@pytest.mark.parametrize(
    ("query", "parameter"),
    [
        ("arrival=2026-07-11", "departure"),
        ("arrival=11/07/2026&departure=2026-07-12", "arrival"),
        ("arrival=2026-07-12&departure=2026-07-11", "departure"),
        ("arrival=2026-07-11&departure=2026-07-12&guests=0", "guests"),
        ("arrival=2026-07-11&departure=2026-07-12&guests=x", "guests"),
    ],
)
def test_bad_parameters_are_named(client, token, query, parameter):
    response = _get(client, f"/api/v1/availability?{query}", token)
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_parameter", "parameter": parameter}


def test_business_rule_errors_keep_their_code(client, token):
    response = _get(client, "/api/v1/availability?arrival=2026-01-01&departure=2026-01-02", token)
    assert response.status_code == 400
    assert response.get_json()["error"] == "reservation.arrival_in_past"


def test_reservations_list_and_detail(client, token, booking):
    data = _get(client, "/api/v1/reservations?status=CONFIRMED&per_page=5", token).get_json()
    assert data["total"] == 1
    assert data["page"] == 1
    listed = data["reservations"][0]
    assert listed["code"] == booking.code
    assert listed["guest"] == "Amira Ben Salah"
    assert listed["nights"] == 3
    detail = _get(client, f"/api/v1/reservations/{booking.id}", token).get_json()
    assert detail["rooms"] == [{"number": "204", "category": "Deluxe", "adults": 2, "children": 0}]
    assert detail["accommodation_millimes"] == 540_000
    assert _get(client, "/api/v1/reservations/999", token).status_code == 404
    filtered = _get(client, "/api/v1/reservations?arriving_from=2026-07-11", token).get_json()
    assert filtered["total"] == 0
    assert _get(client, "/api/v1/reservations?status=NOPE", token).status_code == 400


def test_report_summary(client, token, booking):
    data = _get(
        client, "/api/v1/reports/summary?first=2026-07-10&last=2026-07-12", token
    ).get_json()
    assert data["nights_sold"] == 3
    assert data["nights_sellable"] == 12  # 4 rooms x 3 nights
    assert data["occupancy_basis_points"] == 2500
    assert data["adr_millimes"] == 180_000
    too_long = _get(client, "/api/v1/reports/summary?first=2020-01-01&last=2026-01-01", token)
    assert too_long.status_code == 400


def test_a_token_whose_owner_lost_the_role_is_forbidden_not_crashing(
    client, services, hotel, token
):
    boss = services.users.get_user(hotel.boss, hotel.boss.user.id)
    services.users.create_user(
        hotel.boss,
        username="sami",
        full_name="Sami",
        role="MANAGER",
        temporary_password="cognac-and-cedar-2026",
    )
    services.users.update_user(
        hotel.boss, boss.id, version=boss.version, full_name=boss.full_name, role="RECEPTIONIST"
    )
    assert _get(client, "/api/v1/rooms", token).status_code == 401


# ------------------------------------------------------------ token pages
def test_managers_create_and_revoke_tokens_in_the_interface(signed_in, services, hotel):
    page = signed_in.get("/account/api-tokens").get_data(as_text=True)
    assert "New token" in page
    response = signed_in.post(
        "/account/api-tokens",
        data={
            "name": "Board",
            "days": "30",
            "csrf_token": csrf_token(signed_in, "/account/api-tokens"),
        },
    )
    text = response.get_data(as_text=True)
    assert "It will not be shown again." in text
    secret = text.split('<code class="code-block token" dir="ltr">')[1].split("</code>")[0]
    assert _get(signed_in, "/api/v1/rooms", secret).status_code == 200
    # The list shows only the beginning of the token.
    listing = signed_in.get("/account/api-tokens").get_data(as_text=True)
    assert secret not in listing
    assert secret[:10] in listing
    token_id = services.api_tokens.list_own(hotel.boss)[0].id
    signed_in.post(
        f"/account/api-tokens/{token_id}/revoke",
        data={"csrf_token": csrf_token(signed_in, "/account/api-tokens")},
    )
    assert _get(signed_in, "/api/v1/rooms", secret).status_code == 401
    assert "Revoked" in signed_in.get("/account/api-tokens").get_data(as_text=True)


def test_token_form_errors(signed_in, services, hotel):
    bad = signed_in.post(
        "/account/api-tokens",
        data={"name": "", "days": "7", "csrf_token": csrf_token(signed_in, "/account/api-tokens")},
    )
    assert bad.status_code == 400
    for i in range(10):
        services.api_tokens.create(hotel.boss, name=f"t{i}", days=30)
    full = signed_in.post(
        "/account/api-tokens",
        data={
            "name": "x",
            "days": "30",
            "csrf_token": csrf_token(signed_in, "/account/api-tokens"),
        },
    )
    assert full.headers["Location"] == "/account/api-tokens"
    assert "active tokens" in signed_in.get("/account/api-tokens").get_data(as_text=True)


def test_receptionists_have_no_token_page(client, hotel):
    login(client, "rita")
    assert client.get("/account/api-tokens").status_code in (302, 403)

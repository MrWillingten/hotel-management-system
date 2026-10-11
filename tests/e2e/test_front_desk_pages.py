"""Dashboard, check-in, no-show and housekeeping through HTTP."""

from datetime import timedelta

from hotel.domain.actor import Actor
from tests.conftest import csrf_token, login
from tests.integration.test_booking import book, stay


def _post(client, path, data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def test_dashboard_lists_arrivals_and_checks_in(client, services, hotel):
    r = book(services, hotel, stay(8, 10), "204")
    login(client)
    page = client.get("/").get_data(as_text=True)
    assert "Amira Ben Salah" in page
    assert "Occupancy tonight" in page
    assert "25.0 %" in page  # 1 of 4 rooms
    response = _post(client, f"/reservations/{r.id}/check-in", {"version": r.version, "next": "/"})
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    page = client.get("/").get_data(as_text=True)
    assert "is checked in." in page
    assert "No more arrivals expected today." in page


def test_check_in_never_redirects_off_site(client, services, hotel):
    r = book(services, hotel, stay(8, 10), "204")
    login(client)
    response = _post(
        client,
        f"/reservations/{r.id}/check-in",
        {"version": r.version, "next": "https://evil.example/"},
    )
    assert response.headers["Location"] == f"/reservations/{r.id}"


def test_refused_check_in_shows_the_reason(client, services, hotel):
    r = book(services, hotel, stay(9, 10), "204")
    login(client)
    response = _post(client, f"/reservations/{r.id}/check-in", {"version": r.version})
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Check-in opens on the arrival day" in page


def test_detail_page_warns_about_rooms_not_cleaned(client, services, hotel):
    from hotel.domain.rooms import Housekeeping

    r = book(services, hotel, stay(8, 10), "204")
    services.rooms.set_housekeeping(hotel.rita, hotel.rooms["204"].id, Housekeeping.DIRTY)
    login(client)
    page = client.get(f"/reservations/{r.id}").get_data(as_text=True)
    assert "Not cleaned yet: room 204" in page
    assert "Check in" in page
    assert "Record a no-show" not in page  # before 14:00


def test_no_show_flow(client, services, hotel, clock):
    r = book(services, hotel, stay(8, 10), "204")
    login(client)
    early = client.get(f"/reservations/{r.id}/no-show").get_data(as_text=True)
    assert "A no-show can only be recorded after the check-in time" in early
    clock.advance(timedelta(hours=2))
    login(client)  # the session expired while the clock moved
    detail = client.get(f"/reservations/{r.id}").get_data(as_text=True)
    assert "Record a no-show" in detail
    assert "Cancel reservation" not in detail  # too late to cancel
    page = client.get(f"/reservations/{r.id}/no-show").get_data(as_text=True)
    assert "72.000" in page  # 20 % of 2 x 180
    response = _post(client, f"/reservations/{r.id}/no-show", {"version": r.version})
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "No-show recorded. Fee:" in page
    assert services.reservations.get(Actor.system(), r.id).status == "NO_SHOW"
    again = _post(client, f"/reservations/{r.id}/no-show", {"version": r.version})
    assert "Someone else changed" in client.get(again.headers["Location"]).get_data(as_text=True)


def test_housekeeping_from_the_room_page_and_dashboard(client, services, hotel):
    room_id = hotel.rooms["101"].id
    login(client)
    _post(client, f"/rooms/{room_id}/housekeeping", {"state": "DIRTY"})
    assert "To clean" in client.get("/rooms/").get_data(as_text=True)
    dashboard = client.get("/").get_data(as_text=True)
    assert "Mark clean" in dashboard
    response = _post(client, f"/rooms/{room_id}/housekeeping", {"state": "CLEAN", "next": "/"})
    assert response.headers["Location"] == "/"
    assert "Every room is clean." in client.get("/").get_data(as_text=True)
    # An unknown value is treated as "clean" rather than trusted.
    response = _post(client, f"/rooms/{room_id}/housekeeping", {"state": "<script>"})
    assert response.headers["Location"] == f"/rooms/{room_id}"

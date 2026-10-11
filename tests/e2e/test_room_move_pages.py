"""Moving guests to another room through the pages (story 6.5)."""

import re
from datetime import date, timedelta

from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest
from tests.conftest import csrf_token

_TOKEN = re.compile(r'name="form_token" value="([^"]+)"')


def _booking(services, hotel, arrival=date(2026, 7, 8)):
    reservation = services.reservations.create(
        hotel.boss,
        guest_id=hotel.amira.id,
        period=StayPeriod(arrival, arrival + timedelta(days=3)),
        rooms=[RoomRequest(hotel.rooms["204"].id, 2)],
    )
    return services.reservations.check_in(hotel.boss, reservation.id, version=reservation.version)


def test_move_from_the_reservation_page(signed_in, services, hotel):
    reservation = _booking(services, hotel)
    detail = signed_in.get(f"/reservations/{reservation.id}").get_data(as_text=True)
    move_url = f"/reservations/{reservation.id}/move?room={hotel.rooms['204'].id}"
    assert move_url.replace("&", "&amp;") in detail or move_url in detail
    page = signed_in.get(move_url).get_data(as_text=True)
    assert "205 · Deluxe" in page
    assert "Charge the new room" in page  # managers may charge the upgrade
    data = {
        "csrf_token": csrf_token(signed_in, move_url),
        "form_token": _TOKEN.search(page).group(1),
        "version": reservation.version,
        "room": hotel.rooms["204"].id,
        "to_room": hotel.rooms["205"].id,
    }
    response = signed_in.post(f"/reservations/{reservation.id}/move", data=data)
    assert response.headers["Location"] == f"/reservations/{reservation.id}"
    detail = signed_in.get(response.headers["Location"]).get_data(as_text=True)
    assert "Moved from room 204 to room 205." in detail
    # Sending the same form again moves nothing: 204 is no longer the guests' room.
    again = signed_in.post(f"/reservations/{reservation.id}/move", data=data)
    assert again.headers["Location"] == f"/reservations/{reservation.id}"
    rooms = services.reservations.get(hotel.boss, reservation.id).rooms
    assert [r.number for r in rooms] == ["205"]  # moved on the arrival day: no night in 204


def test_a_double_submit_is_caught(signed_in, services, hotel):
    reservation = _booking(services, hotel)
    url = f"/reservations/{reservation.id}/move?room={hotel.rooms['204'].id}"
    response = signed_in.post(
        url,
        data={
            "csrf_token": csrf_token(signed_in, url),
            "form_token": "already-used",
            "version": reservation.version,
            "to_room": hotel.rooms["205"].id,
        },
    )
    assert "already submitted" in signed_in.get(response.headers["Location"]).get_data(as_text=True)


def test_move_errors_are_shown(signed_in, services, hotel):
    reservation = _booking(services, hotel)
    url = f"/reservations/{reservation.id}/move?room={hotel.rooms['204'].id}"
    page = signed_in.get(url).get_data(as_text=True)
    response = signed_in.post(
        f"/reservations/{reservation.id}/move",
        data={
            "csrf_token": csrf_token(signed_in, url),
            "form_token": _TOKEN.search(page).group(1),
            "version": reservation.version,
            "room": hotel.rooms["204"].id,
            "to_room": hotel.rooms["204"].id,
        },
    )
    assert response.status_code == 200
    assert "already used that room" in response.get_data(as_text=True)


def test_unknown_room_goes_back_to_the_reservation(signed_in, services, hotel):
    reservation = _booking(services, hotel)
    response = signed_in.get(f"/reservations/{reservation.id}/move?room=999")
    assert response.headers["Location"] == f"/reservations/{reservation.id}"


def test_no_free_room_is_explained(signed_in, services, hotel):
    reservation = _booking(services, hotel)
    for number in ("205", "101", "401"):
        services.rooms.schedule_maintenance(
            hotel.boss,
            hotel.rooms[number].id,
            first_night=date(2026, 7, 8),
            reopens_on=date(2026, 7, 12),
            reason="Paint",
        )
    page = signed_in.get(
        f"/reservations/{reservation.id}/move?room={hotel.rooms['204'].id}"
    ).get_data(as_text=True)
    assert "No other room is free" in page

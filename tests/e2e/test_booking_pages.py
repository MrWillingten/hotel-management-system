import re
from urllib.parse import quote

from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest
from tests.conftest import csrf_token, login

PASSWORD = "cognac-and-cedar-2026"


def _signed_in_as_rita(client, services, hotel):
    from hotel.domain.actor import Actor

    services.users.change_own_password(
        Actor(services.users.get_user(hotel.boss, hotel.rita.user_id)),
        current_password=PASSWORD,
        new_password="jasmine tea at noon",
    )
    login(client, "rita", "jasmine tea at noon")
    return client


def _post(client, path, data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def _booking(hotel, room="204", **extra):
    room_id = hotel.rooms[room].id
    return {
        "guest_id": hotel.amira.id,
        "arrival": "2026-07-10",
        "departure": "2026-07-13",
        "room": str(room_id),
        f"adults_{room_id}": "2",
        f"children_{room_id}": "0",
        **extra,
    }


def test_full_booking_flow(client, services, hotel):
    _signed_in_as_rita(client, services, hotel)
    page = client.get("/reservations/new").get_data(as_text=True)
    assert "Choose the dates first." not in page or "Find rooms" in page

    search = client.get(
        "/reservations/new?arrival=2026-07-10&departure=2026-07-13&guests=2&q=amira"
    )
    text = search.get_data(as_text=True)
    assert "Ben Salah" in text  # guest search
    chosen = client.get(
        f"/reservations/new?arrival=2026-07-10&departure=2026-07-13&guests=2"
        f"&guest_id={hotel.amira.id}"
    ).get_data(as_text=True)
    assert "Review the booking" in chosen
    assert "204" in chosen
    assert "401" in chosen

    review = _post(client, "/reservations/review", _booking(hotel))
    text = review.get_data(as_text=True)
    assert review.status_code == 200
    assert "540.000" in text  # 3 nights x 180 DT
    assert "Free cancellation until" in text
    data = dict(re.findall(r'type="hidden" name="([^"]+)" value="([^"]*)"', text))
    created = client.post("/reservations/", data=data)
    assert created.status_code == 302
    detail = client.get(created.headers["Location"]).get_data(as_text=True)
    assert "R-2026-00001" in detail
    assert "Price locked at booking" in detail

    # A double click sends the same token again: refused, no second booking.
    again = client.post("/reservations/", data=data, follow_redirects=True)
    assert "already submitted" in again.get_data(as_text=True)
    assert services.reservations.search(hotel.rita, *_all()).total == 1

    listing = client.get("/reservations/?q=amira&status=CONFIRMED&from=2026-07-01").get_data(
        as_text=True
    )
    assert "R-2026-00001" in listing
    assert client.get("/reservations/?status=BOGUS&from=nope").status_code == 200


def _all():
    from hotel.domain.paging import PageRequest
    from hotel.persistence.repositories.reservations import ReservationFilter

    return ReservationFilter(), PageRequest()


def test_conflict_shows_alternatives(signed_in, services, hotel):
    services.reservations.create(
        hotel.boss,
        guest_id=hotel.karim.id,
        period=StayPeriod(*_dates("2026-07-12", "2026-07-14")),
        rooms=[RoomRequest(hotel.rooms["204"].id, 1)],
    )
    review = _post(signed_in, "/reservations/review", _booking(hotel))
    assert review.status_code == 409
    text = review.get_data(as_text=True)
    assert "Room 204 is already booked" in text
    assert "Rooms free for the same dates" in text


def test_invalid_bookings_are_explained(signed_in, hotel):
    no_room = _post(
        signed_in,
        "/reservations/review",
        {"guest_id": hotel.amira.id, "arrival": "2026-07-10", "departure": "2026-07-13"},
    )
    assert no_room.status_code == 400
    assert "Select at least one room" in no_room.get_data(as_text=True)
    too_many = _post(
        signed_in,
        "/reservations/review",
        _booking(hotel, **{f"adults_{hotel.rooms['204'].id}": "3"}),
    )
    assert "can sleep at most" in too_many.get_data(as_text=True)
    backwards = signed_in.get("/reservations/new?arrival=2026-07-13&departure=2026-07-10")
    assert "after the arrival date" in backwards.get_data(as_text=True)
    stale_token = _post(signed_in, "/reservations/", {**_booking(hotel), "form_token": "forged"})
    assert stale_token.status_code == 302


def test_new_guest_comes_back_to_the_booking(signed_in, hotel):
    back = "/reservations/new?arrival=2026-07-10&departure=2026-07-12"
    response = _post(
        signed_in,
        f"/guests/new?next={quote(back)}",
        {
            "first_name": "Lina",
            "last_name": "Jaziri",
            "id_doc_type": "CIN",
            "id_doc_number": "55556666",
            "nationality": "",
            "phone": "",
            "email": "",
            "notes": "",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].startswith(back + "&guest_id=")
    elsewhere = _post(
        signed_in,
        "/guests/new?next=https://evil.example",
        {
            "first_name": "Mia",
            "last_name": "Jaziri",
            "id_doc_type": "CIN",
            "id_doc_number": "55557777",
            "nationality": "",
            "phone": "",
            "email": "",
            "notes": "",
        },
    )
    assert elsewhere.headers["Location"].startswith("/guests/")


def test_rooms_page_shows_reservations_tonight(signed_in, services, hotel):
    services.reservations.create(
        hotel.boss,
        guest_id=hotel.amira.id,
        period=StayPeriod(*_dates("2026-07-08", "2026-07-09")),
        rooms=[RoomRequest(hotel.rooms["205"].id, 1)],
    )
    assert "Reserved" in signed_in.get("/rooms/").get_data(as_text=True)


def _dates(a, d):
    from datetime import date

    return date.fromisoformat(a), date.fromisoformat(d)

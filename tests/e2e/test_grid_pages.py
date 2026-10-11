from tests.integration.test_booking import book, stay


def test_grid_page(signed_in, services, hotel):
    r = book(services, hotel, stay(9, 11), "204")
    page = signed_in.get("/availability/").get_data(as_text=True)
    assert f"/reservations/{r.id}" in page
    assert "Ben Salah" in page
    assert "/reservations/new?arrival=2026-07-08&amp;departure=2026-07-09" in page
    assert signed_in.get("/availability/?start=2026-07-20").status_code == 200
    assert signed_in.get("/availability/?start=garbage").status_code == 200


def test_guest_page_lists_reservations(signed_in, services, hotel):
    r = book(services, hotel, stay(9, 11), "204")
    page = signed_in.get(f"/guests/{hotel.amira.id}").get_data(as_text=True)
    assert r.code in page
    assert "New reservation" in page


def test_room_edit_explains_blocking_bookings(signed_in, services, hotel):
    from tests.conftest import csrf_token

    r = book(services, hotel, stay(15, 17), "204")
    room = hotel.rooms["204"]
    response = signed_in.post(
        f"/rooms/{room.id}/edit",
        data={
            "csrf_token": csrf_token(signed_in, "/"),
            "version": room.version,
            "number": "204",
            "category_id": room.category_id,
            "capacity": "2",
            "nightly_rate": "180",
            "notes": "",
        },
    )
    assert response.status_code == 400
    assert r.code in response.get_data(as_text=True)

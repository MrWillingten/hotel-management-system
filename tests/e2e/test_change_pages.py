import re

from tests.conftest import csrf_token
from tests.integration.test_booking import book, stay


def _post(client, path, data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def _hidden(text):
    return dict(re.findall(r'type="hidden" name="([^"]+)" value="([^"]*)"', text))


def test_change_flow(signed_in, services, hotel):
    r = book(services, hotel, stay(10, 13), "204")
    form = signed_in.get(f"/reservations/{r.id}/edit").get_data(as_text=True)
    assert "Check availability and price" in form
    review = _post(
        signed_in,
        f"/reservations/{r.id}/edit",
        {
            "arrival": "2026-07-10",
            "departure": "2026-07-15",
            "room_0": str(hotel.rooms["204"].id),
            "adults_0": "2",
            "children_0": "0",
        },
    )
    text = review.get_data(as_text=True)
    assert "900.000" in text  # 5 nights x 180 DT
    saved = signed_in.post(f"/reservations/{r.id}/change", data=_hidden(text))
    assert saved.status_code == 302
    assert "900.000" in signed_in.get(saved.headers["Location"]).get_data(as_text=True)
    again = signed_in.post(f"/reservations/{r.id}/change", data=_hidden(text))
    assert again.status_code == 302  # token already used: no second change


def test_change_refused_shows_why(signed_in, services, hotel):
    r = book(services, hotel, stay(10, 13), "204")
    book(services, hotel, stay(13, 15), "204", guest=hotel.karim)
    review = _post(
        signed_in,
        f"/reservations/{r.id}/edit",
        {
            "arrival": "2026-07-10",
            "departure": "2026-07-15",
            "room_0": str(hotel.rooms["204"].id),
            "adults_0": "1",
        },
    )
    assert review.status_code == 409
    assert "already booked" in review.get_data(as_text=True)
    empty = _post(
        signed_in,
        f"/reservations/{r.id}/edit",
        {"arrival": "2026-07-10", "departure": "2026-07-12", "room_0": ""},
    )
    assert empty.status_code == 400


def test_cancel_flow(signed_in, services, hotel):
    r = book(services, hotel, stay(9, 11), "204")  # arrival tomorrow: fee applies
    page = signed_in.get(f"/reservations/{r.id}/cancel").get_data(as_text=True)
    assert "Arrival is close" in page
    assert "(20\u00a0% of the accommodation)" in page
    assert "72.000" in page  # 20 % of 360 DT
    done = signed_in.post(f"/reservations/{r.id}/cancel", data=_hidden(page))
    assert done.status_code == 302
    detail = signed_in.get(done.headers["Location"]).get_data(as_text=True)
    assert "Cancelled" in detail
    assert "72.000" in detail
    after = signed_in.get(f"/reservations/{r.id}/cancel").get_data(as_text=True)
    assert "Only a confirmed reservation can be cancelled." in after
    replay = signed_in.post(f"/reservations/{r.id}/cancel", data=_hidden(page))
    assert replay.status_code == 302


def test_free_cancellation_message(signed_in, services, hotel):
    r = book(services, hotel, stay(20, 22), "204")
    page = signed_in.get(f"/reservations/{r.id}/cancel").get_data(as_text=True)
    assert "Cancelling now is free" in page

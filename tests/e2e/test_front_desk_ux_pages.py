"""Sprint 7 batch A (stories 7.1-7.4): dashboard lists, fewer wrong clicks, the grid."""

from datetime import timedelta

from hotel.domain.billing import PaymentMethod
from hotel.domain.money import Money
from tests.conftest import csrf_token, login
from tests.integration.test_booking import book, stay

NBSP = " "


def _post(client, path, data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def _in_house(services, hotel, period, number="204"):
    r = book(services, hotel, period, number)
    return services.reservations.check_in(hotel.rita, r.id, version=r.version)


def test_in_house_list_and_the_cards_that_lead_to_it(client, services, hotel):
    _in_house(services, hotel, stay(8, 10))
    login(client)
    page = client.get("/").get_data(as_text=True)
    assert 'id="in-house"' in page
    # Both "Guests in the house" and "Due from guests in the house" lead to it (7.1).
    assert page.count('href="#in-house"') == 2
    in_house = page.split('id="in-house"')[1].split("</section>")[0]
    assert "Amira Ben Salah" in in_house
    assert f"Balance due: <bdi>360.000{NBSP}DT</bdi>" in in_house


def test_departure_rows_show_the_balance_then_paid(client, services, hotel, clock):
    r = _in_house(services, hotel, stay(8, 9))
    clock.advance(timedelta(days=1))  # departure day
    login(client)
    departures = client.get("/").get_data(as_text=True).split('id="departures"')[1]
    departures = departures.split("</section>")[0]
    assert f"Balance due: <bdi>180.000{NBSP}DT</bdi>" in departures
    assert "Check out · <bdi>204</bdi>" in departures  # 7.2
    services.billing.record_payment(
        hotel.rita, r.id, amount=Money.from_dinars(180), method=PaymentMethod.CASH
    )
    departures = client.get("/").get_data(as_text=True).split('id="departures"')[1]
    assert ">Paid</span>" in departures.split("</section>")[0]


def test_buttons_and_messages_name_the_room(client, services, hotel):
    r = book(services, hotel, stay(8, 10), "205")
    login(client)
    page = client.get("/").get_data(as_text=True)
    assert "Check in · <bdi>205</bdi>" in page
    _post(client, f"/reservations/{r.id}/check-in", {"version": r.version, "next": "/"})
    assert "Amira Ben Salah is checked in, room 205." in client.get("/").get_data(as_text=True)
    r = services.reservations.get(hotel.rita, r.id)
    response = _post(client, f"/reservations/{r.id}/check-out", {"version": r.version})
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Amira Ben Salah has checked out of room 205. Invoice F-2026-00001 issued." in page


def test_actions_that_end_a_stay_are_kept_apart(client, services, hotel):
    r = book(services, hotel, stay(12, 14), "204")
    login(client)
    page = client.get(f"/reservations/{r.id}").get_data(as_text=True)
    top, _, bottom = page.partition('id="other-actions"')
    assert "Cancel reservation" not in top
    assert "Cancel reservation" in bottom
    assert top.split('class="page-actions"')[1].count("button--primary") == 0  # not arrived yet
    checked_in = _in_house(services, hotel, stay(8, 10), "205")
    page = client.get(f"/reservations/{checked_in.id}").get_data(as_text=True)
    actions = page.split('class="page-actions"')[1].split("</div>\n</div>")[0]
    assert actions.count("button--primary") == 1  # only Check out
    assert 'id="other-actions"' not in page


def test_grid_filters_by_category_and_marks_reserved_nights(signed_in, services, hotel):
    book(services, hotel, stay(9, 11), "204")
    deluxe = hotel.rooms["204"].category_id
    page = signed_in.get(f"/availability/?category={deluxe}").get_data(as_text=True)
    assert ">204</a>" in page
    assert ">101</a>" not in page
    assert "cell--reserved" in page
    assert f'value="{deluxe}" selected' in page
    everything = signed_in.get("/availability/?category=999").get_data(as_text=True)
    assert ">101</a>" in everything


def test_reserved_and_occupied_differ_by_pattern_not_only_colour(client):
    response = client.get("/static/css/app.css")
    css = response.get_data(as_text=True)
    response.close()  # static files are streamed: close the file handle
    reserved = css.split(".cell--reserved {")[1].split("}")[0]
    assert "background-image: radial-gradient" in reserved

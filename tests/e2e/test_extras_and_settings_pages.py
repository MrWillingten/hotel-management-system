"""Catalogue, charges, settings and tax rules through HTTP."""

import re

from hotel.domain.money import Money
from tests.conftest import csrf_token, login
from tests.e2e.test_booking_pages import _signed_in_as_rita
from tests.integration.test_booking import book, stay

_TOKEN = re.compile(r'name="form_token" value="([^"]+)"')


def _post(client, path, data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def test_manager_builds_the_catalogue(client, services, hotel):
    login(client)
    response = _post(client, "/extras/", {"name": "Breakfast", "unit_price": "15,5"})
    assert response.status_code == 302
    page = client.get("/extras/").get_data(as_text=True)
    assert "Breakfast" in page
    assert "15.500\u00a0DT" in page
    bad = _post(client, "/extras/", {"name": "", "unit_price": "abc"})
    assert bad.status_code == 400
    [extra] = services.extras.catalogue(hotel.boss)
    response = _post(
        client,
        f"/extras/{extra.id}/edit",
        {"version": extra.version, "name": "Breakfast", "unit_price": "16"},
    )
    assert response.status_code == 302
    assert not services.extras.get(hotel.boss, extra.id).is_active  # box left unticked
    assert client.get("/extras/999/edit").status_code == 404


def test_receptionists_cannot_open_the_catalogue_or_settings(client, services, hotel):
    _signed_in_as_rita(client, services, hotel)
    assert client.get("/extras/").status_code == 403
    assert client.get("/settings/").status_code == 403


def test_charge_from_the_reservation_page(client, services, hotel):
    services.extras.create(hotel.boss, name="Breakfast", unit_price=Money.from_dinars(15))
    [breakfast] = services.extras.catalogue(hotel.boss)
    r = book(services, hotel, stay(8, 10), "204")
    services.reservations.check_in(hotel.rita, r.id, version=r.version)
    login(client)
    page = client.get(f"/reservations/{r.id}").get_data(as_text=True)
    token = _TOKEN.search(page).group(1)
    data = {
        "form_token": token,
        "extra_id": breakfast.id,
        "quantity": "2",
        "charge_date": "2026-07-08",
    }
    response = _post(client, f"/reservations/{r.id}/charges", data)
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Charged: 2 × Breakfast." in page
    assert "30.000\u00a0DT" in page
    again = _post(client, f"/reservations/{r.id}/charges", data)  # double click
    assert "already submitted" in client.get(again.headers["Location"]).get_data(as_text=True)
    assert len(services.extras.charges_for(hotel.boss, r.id)) == 1
    [charge] = services.extras.charges_for(hotel.boss, r.id)
    response = _post(
        client, f"/reservations/charges/{charge.id}/void", {"reservation_id": r.id, "reason": "x"}
    )
    assert "Charge voided." in client.get(response.headers["Location"]).get_data(as_text=True)


def test_refused_charge_explains_why(client, services, hotel):
    services.extras.create(hotel.boss, name="Breakfast", unit_price=Money.from_dinars(15))
    [breakfast] = services.extras.catalogue(hotel.boss)
    r = book(services, hotel, stay(8, 10), "204")
    services.reservations.check_in(hotel.rita, r.id, version=r.version)
    login(client)
    token = _TOKEN.search(client.get(f"/reservations/{r.id}").get_data(as_text=True)).group(1)
    response = _post(
        client,
        f"/reservations/{r.id}/charges",
        {"form_token": token, "extra_id": breakfast.id, "quantity": "0"},
    )
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "The quantity must be between 1 and 99." in page


def test_settings_page(client, services, hotel):
    login(client)
    page = client.get("/settings/").get_data(as_text=True)
    assert 'value="14:00"' in page
    assert 'value="20"' in page
    response = _post(
        client,
        "/settings/",
        {
            "check_in_time": "15:00",
            "check_out_time": "11:00",
            "cancellation_fee": "25,5",
            "cancellation_window_hours": "72",
            "grace_period_hours": "0",
            "discount_cap": "30",
        },
    )
    assert response.status_code == 302
    settings = services.hotel_settings.get(hotel.boss)
    assert (settings.cancellation_fee_bp, settings.cancellation_window_hours) == (2550, 72)
    bad = _post(
        client,
        "/settings/",
        {
            "check_in_time": "25:00",
            "check_out_time": "11:00",
            "cancellation_fee": "101",
            "cancellation_window_hours": "72",
            "grace_period_hours": "0",
            "discount_cap": "30",
        },
    )
    assert bad.status_code == 400


def test_tax_rules_pages(client, services, hotel):
    login(client)
    response = _post(
        client,
        "/settings/taxes",
        {"name": "VAT", "kind": "PERCENT", "rate": "7", "applies_to": "ACCOMMODATION"},
    )
    assert response.status_code == 302
    _post(
        client,
        "/settings/taxes",
        {
            "name": "Tourist tax",
            "kind": "PER_ADULT_NIGHT",
            "rate": "3",
            "applies_to": "ACCOMMODATION",
        },
    )
    page = client.get("/settings/").get_data(as_text=True)
    assert "7\u00a0%" in page
    assert "3.000\u00a0DT per adult per night" in page
    bad = _post(client, "/settings/taxes", {"name": "X", "kind": "NOPE", "rate": "1"})
    assert bad.status_code == 400
    vat = services.hotel_settings.tax_rules(hotel.boss)[0]
    assert 'value="7"' in client.get(f"/settings/taxes/{vat.id}/edit").get_data(as_text=True)
    response = _post(
        client,
        f"/settings/taxes/{vat.id}/edit",
        {
            "version": vat.version,
            "name": "VAT",
            "kind": "PERCENT",
            "rate": "7,5",
            "applies_to": "SERVICES",
        },
    )
    assert response.status_code == 302
    updated = services.hotel_settings.tax_rules(hotel.boss)
    assert any(r.name == "VAT" and r.rate_bp == 750 and not r.is_active for r in updated)
    assert client.get("/settings/taxes/999/edit").status_code == 404

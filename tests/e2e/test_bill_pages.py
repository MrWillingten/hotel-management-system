"""The bill page: preview, payments, refunds and discounts through HTTP."""

import re

from hotel.domain.billing import PaymentMethod
from hotel.domain.money import Money
from hotel.domain.taxes import PercentTax
from tests.conftest import csrf_token, login
from tests.e2e.test_booking_pages import _signed_in_as_rita
from tests.integration.test_booking import book, stay

_TOKEN = re.compile(r'name="form_token" value="([^"]+)"')
NBSP = " "


def _post(client, path, data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def _token(client, reservation_id):
    page = client.get(f"/reservations/{reservation_id}/bill").get_data(as_text=True)
    return _TOKEN.search(page).group(1)


def test_bill_preview_and_deposit(client, services, hotel):
    services.hotel_settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    r = book(services, hotel, stay(9, 11), "204")  # 2 x 180
    login(client)
    page = client.get(f"/reservations/{r.id}/bill").get_data(as_text=True)
    assert "Room 204" in page
    assert f"2 × <bdi>180.000{NBSP}DT</bdi>" in page
    assert f"VAT (7{NBSP}%)" in page
    assert f"385.200{NBSP}DT" in page  # 360 + 25.200
    assert "Record a deposit" in page
    response = _post(
        client,
        f"/reservations/{r.id}/payments",
        {"form_token": _token(client, r.id), "amount": "100", "method": "CARD", "reference": "A1"},
    )
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert f"Received 100.000{NBSP}DT." in page
    assert "Deposit" in page
    assert "Card" in page
    detail = client.get(f"/reservations/{r.id}").get_data(as_text=True)
    assert f"285.200{NBSP}DT" in detail  # balance due on the reservation page


def test_refused_payment_and_unknown_method(client, services, hotel):
    r = book(services, hotel, stay(9, 10), "101")  # 120 DT
    login(client)
    response = _post(
        client,
        f"/reservations/{r.id}/payments",
        {"form_token": _token(client, r.id), "amount": "500", "method": "CASH"},
    )
    assert "more than the balance due (120.000 DT)" in client.get(
        response.headers["Location"]
    ).get_data(as_text=True)
    response = _post(
        client,
        f"/reservations/{r.id}/payments",
        {"form_token": _token(client, r.id), "amount": "10", "method": "BITCOIN"},
    )
    assert "Choose how the money was paid." in client.get(response.headers["Location"]).get_data(
        as_text=True
    )


def test_double_submitted_payment_is_recorded_once(client, services, hotel):
    r = book(services, hotel, stay(9, 10), "101")
    login(client)
    data = {"form_token": _token(client, r.id), "amount": "10", "method": "CASH"}
    _post(client, f"/reservations/{r.id}/payments", data)
    again = _post(client, f"/reservations/{r.id}/payments", data)
    assert "already submitted" in client.get(again.headers["Location"]).get_data(as_text=True)
    assert services.billing.bill(hotel.boss, r.id).paid == Money.from_dinars(10)


def test_discount_and_refund_pages(client, services, hotel):
    r = book(services, hotel, stay(9, 11), "204")  # 360 DT
    services.billing.record_payment(
        hotel.rita, r.id, amount=Money.from_dinars(360), method=PaymentMethod.CASH
    )
    login(client)
    response = _post(
        client,
        f"/reservations/{r.id}/discounts",
        {"kind": "PERCENT", "value": "10", "reason": "Returning guest"},
    )
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Discount granted." in page
    assert "Discount: Returning guest" in page
    assert "Refund owed to the guest" in page
    response = _post(
        client,
        f"/reservations/{r.id}/refunds",
        {"form_token": _token(client, r.id), "amount": "36", "method": "CASH"},
    )
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert f"Refunded 36.000{NBSP}DT." in page
    assert "The bill is settled." in page
    over = _post(
        client, f"/reservations/{r.id}/discounts", {"kind": "FIXED", "value": "200", "reason": "x"}
    )
    assert "above the allowed maximum" in client.get(over.headers["Location"]).get_data(
        as_text=True
    )
    [discount] = services.billing.discounts(hotel.boss, r.id)
    response = _post(
        client, f"/reservations/discounts/{discount.id}/remove", {"reservation_id": r.id}
    )
    assert "Discount removed." in client.get(response.headers["Location"]).get_data(as_text=True)


def test_receptionists_cannot_refund_or_discount(client, services, hotel):
    r = book(services, hotel, stay(9, 11), "204")
    _signed_in_as_rita(client, services, hotel)
    page = client.get(f"/reservations/{r.id}/bill").get_data(as_text=True)
    assert "Grant a discount" not in page
    for path in (f"/reservations/{r.id}/refunds", f"/reservations/{r.id}/discounts"):
        assert _post(client, path, {"amount": "1", "method": "CASH"}).status_code == 403

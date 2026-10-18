"""Check-out, invoice and invoice list pages."""

from datetime import timedelta

from hotel.domain.money import Money
from tests.conftest import csrf_token, login
from tests.integration.test_booking import book, stay

NBSP = " "


def _post(client, path, data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def _in_house(services, hotel, period):
    r = book(services, hotel, period, "204")
    return services.reservations.check_in(hotel.rita, r.id, version=r.version)


def test_check_out_flow_and_invoice_page(client, services, hotel, clock):
    r = _in_house(services, hotel, stay(8, 10))
    clock.advance(timedelta(days=1))  # leaves one day early
    login(client)
    dashboard = client.get("/").get_data(as_text=True)
    assert "360.000 DT" in dashboard  # due from guests in the house (may wrap before "DT")
    page = client.get(f"/reservations/{r.id}/check-out").get_data(as_text=True)
    assert "Early departure" in page
    assert f"<bdi>180.000{NBSP}DT</bdi> is still due" in page
    response = _post(client, f"/reservations/{r.id}/check-out", {"version": r.version})
    assert response.status_code == 302
    invoice_page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Invoice F-2026-00001 issued." in invoice_page
    assert "Room 204" in invoice_page
    assert "Ctrl+P" in invoice_page
    # Story 6.13: a branded sheet with the guest, the stay and a payment stamp.
    assert 'class="invoice-doc"' in invoice_page
    assert "Billed to" in invoice_page
    assert "Nights: 1" in invoice_page
    assert "invoice-doc__stamp--due" in invoice_page  # 180 DT still due
    detail = client.get(f"/reservations/{r.id}").get_data(as_text=True)
    assert "Invoice F-2026-00001" in detail
    assert "Unpaid after departure" in client.get("/").get_data(as_text=True)
    listing = client.get("/invoices/?q=F-2026").get_data(as_text=True)
    assert "F-2026-00001" in listing
    assert f"180.000{NBSP}DT" in listing


def test_check_out_of_a_reservation_not_in_the_house_is_explained(client, services, hotel):
    r = book(services, hotel, stay(9, 10), "204")
    login(client)
    response = client.get(f"/reservations/{r.id}/check-out")
    assert response.status_code == 302
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "isn&#39;t possible" in page
    response = _post(client, f"/reservations/{r.id}/check-out", {"version": r.version})
    assert response.headers["Location"] == f"/reservations/{r.id}"


def test_settled_check_out_has_no_warning(client, services, hotel):
    r = _in_house(services, hotel, stay(8, 9))
    from hotel.domain.billing import PaymentMethod

    services.billing.record_payment(
        hotel.rita, r.id, amount=Money.from_dinars(180), method=PaymentMethod.CARD
    )
    login(client)
    page = client.get(f"/reservations/{r.id}/check-out").get_data(as_text=True)
    assert "still due" not in page
    assert "Early departure" not in page
    response = _post(client, f"/reservations/{r.id}/check-out", {"version": r.version})
    invoice_page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Paid in full" in invoice_page
    assert "Payments received" in invoice_page


def test_unknown_invoice_is_a_404(client, manager):
    login(client)
    assert client.get("/invoices/42").status_code == 404
    assert "No invoice yet" in client.get("/invoices/").get_data(as_text=True)


def test_print_stylesheet_hides_the_interface(client):
    css = client.get("/static/css/app.css")
    text = css.get_data(as_text=True)
    css.close()
    assert "@media print" in text
    assert "size: A4" in text  # invoices print on A4 with page numbers
    assert "counter(pages)" in text

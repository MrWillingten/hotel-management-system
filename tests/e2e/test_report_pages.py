"""The Reports page (story 5.1)."""

from tests.conftest import login
from tests.e2e.test_booking_pages import _signed_in_as_rita
from tests.integration.test_booking import book, stay


def test_reports_page_shows_the_figures(client, services, hotel):
    book(services, hotel, stay(8, 10), "204")
    login(client)
    page = client.get("/reports/").get_data(as_text=True)
    assert "Occupancy per day" in page
    assert "Nights sold: 2 of 124" in page  # July: 31 nights x 4 rooms
    assert "Deluxe" in page
    long = client.get("/reports/?first=2026-01-01&last=2026-12-31").get_data(as_text=True)
    assert "Occupancy per month" in long


def test_reports_refuse_bad_ranges_and_receptionists(client, services, hotel):
    login(client)
    response = client.get("/reports/?first=2026-07-10&last=2026-07-01")
    assert response.status_code == 400
    assert "must not be before the first night" in response.get_data(as_text=True)
    assert client.get("/reports/?first=2020-01-01&last=2026-01-01").status_code == 400
    assert client.get("/reports/?first=nope").status_code == 400


def test_receptionists_cannot_open_reports(client, services, hotel):
    _signed_in_as_rita(client, services, hotel)
    assert client.get("/reports/").status_code == 403


def test_room_form_links_to_categories(client, manager):
    login(client)
    page = client.get("/rooms/new").get_data(as_text=True)
    assert "Manage categories" in page


def test_csv_export_is_safe_audited_and_manager_only(client, services, hotel):
    from hotel.domain.money import Money

    # Guest names only accept letters, but category names are free text.
    evil = services.rooms.create_category(hotel.boss, name="=HYPERLINK(1)")
    hotel.rooms["666"] = services.rooms.create_room(
        hotel.boss, number="666", category_id=evil.id, capacity=2, nightly_rate=Money(100_000)
    )
    r = book(services, hotel, stay(8, 9), "666")
    r = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    services.invoices.check_out(hotel.rita, r.id, version=r.version)
    login(client)
    response = client.get("/reports/categories.csv?first=2026-07-01&last=2026-07-31")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    text = response.get_data(as_text=True)
    assert text.startswith("\ufeffcategory,nights_sold,room_value_dt")
    assert "'=HYPERLINK(1),1,100.000" in text
    outstanding = client.get("/reports/outstanding.csv?first=2026-07-01&last=2026-07-31")
    assert "09123456" not in outstanding.get_data(as_text=True)  # never a document number
    occupancy = client.get("/reports/occupancy.csv?first=2026-07-08&last=2026-07-09").get_data(
        as_text=True
    )
    assert "2026-07-08,1,5,20.0,100.000" in occupancy
    assert client.get("/reports/secrets.csv?first=2026-07-01&last=2026-07-02").status_code == 404
    with services.uow_factory() as uow:
        assert [e.action for e in uow.audit.iterate()][-1] == "report.exported"


def test_csv_neutralises_formulas():
    from hotel.domain.money import Money
    from hotel.web.csv_export import safe_cell, to_csv

    for dangerous in ("=1+1", "+33", "-2", "@SUM(A1)", "\tx", "\rx"):
        assert safe_cell(dangerous) == "'" + dangerous
    assert safe_cell("Deluxe") == "Deluxe"
    assert safe_cell(Money(-12_500)) == "-12.500"  # our own numbers stay numbers
    assert safe_cell(7) == "7"
    assert safe_cell(None) == ""
    assert to_csv(["a"], [["=x"]]) == "﻿a\r\n'=x\r\n"


def test_night_audit_page_and_command(client, services, hotel, clock, monkeypatch, capsys):
    from datetime import timedelta

    book(services, hotel, stay(8, 10), "204")
    clock.advance(timedelta(days=1))
    login(client)
    from tests.conftest import csrf_token

    page = client.get("/night-audit/").get_data(as_text=True)
    assert "No day closed yet." in page
    response = client.post(
        "/night-audit/", data={"csrf_token": csrf_token(client, "/"), "day": "2026-07-08"}
    )
    assert "Day closed." in response.get_data(as_text=True)
    again = client.post(
        "/night-audit/", data={"csrf_token": csrf_token(client, "/"), "day": "2026-07-08"}
    )
    assert "already closed" in again.get_data(as_text=True)
    future = client.post(
        "/night-audit/", data={"csrf_token": csrf_token(client, "/"), "day": "2026-07-09"}
    )
    assert future.status_code == 400

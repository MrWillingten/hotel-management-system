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

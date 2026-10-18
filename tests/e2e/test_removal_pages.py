"""Delete or archive through the pages (story 6.17)."""

from hotel.domain.enums import Role
from hotel.domain.guests import GuestDetails
from hotel.domain.money import Money
from hotel.domain.taxes import PercentTax
from tests.conftest import MANAGER_PASSWORD, csrf_token, login
from tests.integration.test_booking import book, stay


def _remove(client, url, *, confirm=True):
    data = {"csrf_token": csrf_token(client, url)}
    if confirm:
        data["confirm"] = "on"
    return client.post(url, data=data)


def test_a_never_used_guest_is_deleted_after_confirmation(signed_in, services, hotel):
    lina = services.guests.register(hotel.boss, GuestDetails("Lina", "Trabelsi", "CIN", "07654321"))
    detail = signed_in.get(f"/guests/{lina.id}").get_data(as_text=True)
    assert f'href="/guests/{lina.id}/remove"' in detail
    url = f"/guests/{lina.id}/remove"
    page = signed_in.get(url).get_data(as_text=True)
    assert "deleted permanently" in page
    assert "Delete permanently" in page
    unconfirmed = _remove(signed_in, url, confirm=False)
    assert unconfirmed.headers["Location"] == url
    response = _remove(signed_in, url)
    assert response.headers["Location"] == "/guests/"
    assert "Guest deleted." in signed_in.get("/guests/").get_data(as_text=True)


def test_a_guest_with_history_is_archived_listed_apart_and_restored(signed_in, services, hotel):
    r = book(services, hotel, stay(8, 9), "204")
    page = signed_in.get(f"/guests/{hotel.amira.id}/remove").get_data(as_text=True)
    assert "stay in progress or to come" in page  # blocked while the stay is to come
    services.reservations.cancel(hotel.boss, r.id, version=r.version)
    url = f"/guests/{hotel.amira.id}/remove"
    page = signed_in.get(url).get_data(as_text=True)
    assert "archived, not deleted" in page
    assert "Stays: 1" in page
    _remove(signed_in, url)
    listing = signed_in.get("/guests/").get_data(as_text=True)
    assert "Amira" not in listing
    assert "Archived: 1" in listing
    assert "Amira" in signed_in.get("/guests/?archived=1").get_data(as_text=True)
    detail = signed_in.get(f"/guests/{hotel.amira.id}").get_data(as_text=True)
    assert "Archived on" in detail
    assert "Edit guest" not in detail
    signed_in.post(
        f"/guests/{hotel.amira.id}/restore",
        data={"csrf_token": csrf_token(signed_in, f"/guests/{hotel.amira.id}")},
    )
    assert "Amira" in signed_in.get("/guests/").get_data(as_text=True)


def test_rooms_extras_taxes_and_staff_have_the_same_flow(signed_in, services, hotel):
    room = services.rooms.create_room(
        hotel.boss,
        number="999",
        category_id=hotel.rooms["101"].category_id,
        capacity=2,
        nightly_rate=Money.from_dinars(90),
    )
    extra = services.extras.create(hotel.boss, name="Spa", unit_price=Money.from_dinars(40))
    tax = services.hotel_settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    newcomer = services.users.create_user(
        hotel.boss,
        username="sami",
        full_name="Sami",
        role=Role.RECEPTIONIST,
        temporary_password=MANAGER_PASSWORD,
    )
    for url, done, listing in (
        (f"/rooms/{room.id}/remove", "Room deleted.", "/rooms/"),
        (f"/extras/{extra.id}/remove", "Service deleted.", "/extras/"),
        (f"/settings/taxes/{tax.id}/remove", "Tax rule deleted.", "/settings/"),
        (f"/staff/{newcomer.id}/remove", "Account deleted.", "/staff/"),
    ):
        assert "Delete permanently" in signed_in.get(url).get_data(as_text=True), url
        response = _remove(signed_in, url)
        assert response.headers["Location"] == listing, url
        assert done in signed_in.get(listing).get_data(as_text=True), url


def test_removing_oneself_is_explained(signed_in, hotel):
    page = signed_in.get(f"/staff/{hotel.boss.user.id}/remove").get_data(as_text=True)
    assert "cannot remove your own account" in page


def test_receptionists_cannot_remove_anything(client, hotel):
    login(client, "rita")
    own = "olive-grove-at-dusk-7"
    client.post(
        "/account/password",
        data={
            "current_password": MANAGER_PASSWORD,
            "password": own,
            "confirm": own,
            "csrf_token": csrf_token(client, "/account/password"),
        },
    )
    assert client.get(f"/guests/{hotel.amira.id}/remove").status_code == 403
    assert client.get(f"/rooms/{hotel.rooms['204'].id}/remove").status_code == 403
    assert "Remove…" not in client.get(f"/guests/{hotel.amira.id}").get_data(as_text=True)

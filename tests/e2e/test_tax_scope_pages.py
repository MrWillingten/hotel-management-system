"""Taxes by guest and per stay, through the pages (story 6.16)."""

from datetime import date

from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest
from hotel.domain.taxes import PerAdultNightTax, TaxPayers
from tests.conftest import csrf_token


def test_a_tax_rule_says_who_pays(signed_in, services, hotel):
    page = signed_in.get("/settings/").get_data(as_text=True)
    assert "Guests not from Tunisia" in page
    response = signed_in.post(
        "/settings/taxes",
        data={
            "name": "Tourist tax",
            "kind": "PER_ADULT_NIGHT",
            "rate": "3",
            "applies_to": "ACCOMMODATION",
            "payers": "FOREIGN",
            "csrf_token": csrf_token(signed_in, "/settings/"),
        },
    )
    assert response.status_code == 302
    rule = services.hotel_settings.tax_rules(hotel.boss)[0]
    assert rule.payers is TaxPayers.FOREIGN
    edit = signed_in.get(f"/settings/taxes/{rule.id}/edit").get_data(as_text=True)
    assert '<option value="FOREIGN" selected>' in edit


def test_the_hotel_country_is_typed_by_name(signed_in, services, hotel):
    page = signed_in.get("/settings/").get_data(as_text=True)
    assert 'value="Tunisia"' in page
    data = {
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "cancellation_fee": "20",
        "cancellation_window_hours": "48",
        "grace_period_hours": "0",
        "discount_cap": "30",
        "weekend_surcharge": "0",
        "anonymise_after_months": "24",
        "home_country": "Maroc",
        "csrf_token": csrf_token(signed_in, "/settings/"),
    }
    assert signed_in.post("/settings/", data=data).status_code == 302
    assert services.hotel_settings.get(hotel.boss).home_country == "MA"
    data["home_country"] = "Atlantis"
    data["csrf_token"] = csrf_token(signed_in, "/settings/")
    assert signed_in.post("/settings/", data=data).status_code == 400


def test_a_manager_exempts_a_stay_on_its_bill(signed_in, services, hotel):
    tourist = services.hotel_settings.create_tax_rule(
        hotel.boss, PerAdultNightTax(name="Tourist tax", amount_per=Money.from_dinars(3))
    )
    r = services.reservations.create(
        hotel.boss,
        guest_id=hotel.amira.id,
        period=StayPeriod(date(2026, 7, 8), date(2026, 7, 10)),
        rooms=[RoomRequest(hotel.rooms["204"].id, 2)],
    )
    url = f"/reservations/{r.id}/bill"
    page = signed_in.get(url).get_data(as_text=True)
    assert "Exempt this stay" in page
    assert page.count('id="f-reason"') == 1  # the discount form's; no duplicate ids
    response = signed_in.post(
        f"/reservations/{r.id}/tax-exemptions",
        data={
            "tax_rule_id": tourist.id,
            "exemption_reason": "Child",
            "csrf_token": csrf_token(signed_in, url),
        },
    )
    page = signed_in.get(response.headers["Location"]).get_data(as_text=True)
    assert "The stay is exempt from this tax." in page
    assert "Apply the tax again" in page
    exemption = services.billing.exemptions(hotel.boss, r.id)[0]
    response = signed_in.post(
        f"/reservations/tax-exemptions/{exemption.id}/remove",
        data={"reservation_id": r.id, "csrf_token": csrf_token(signed_in, url)},
    )
    assert "applies to this stay again" in signed_in.get(response.headers["Location"]).get_data(
        as_text=True
    )
    duplicate = signed_in.post(
        f"/reservations/{r.id}/tax-exemptions",
        data={
            "tax_rule_id": 999,
            "exemption_reason": "x",
            "csrf_token": csrf_token(signed_in, url),
        },
    )
    assert duplicate.status_code == 302  # refused with a message, not a crash

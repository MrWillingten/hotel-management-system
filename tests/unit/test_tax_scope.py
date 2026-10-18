"""Who pays a tax (story 6.16): pure rules."""

import pytest

from hotel.domain.errors import ValidationError
from hotel.domain.money import Money
from hotel.domain.settings import HotelSettings
from hotel.domain.taxes import (
    PerAdultNightTax,
    PercentTax,
    TaxExemption,
    TaxPayers,
    is_national,
    taxes_for_stay,
)


def _rules():
    return [
        PercentTax(id=1, name="VAT", rate_bp=700),
        PerAdultNightTax(
            id=2, name="Tourist tax", amount_per=Money(3000), payers=TaxPayers.FOREIGN
        ),
        PercentTax(id=3, name="Local levy", rate_bp=100, payers=TaxPayers.NATIONALS),
        PercentTax(id=4, name="Old", rate_bp=100, is_active=False),
    ]


def test_each_rule_concerns_its_payers():
    vat, tourist, local, _ = _rules()
    assert vat.concerns(national=True) and vat.concerns(national=False)  # noqa: PT018
    assert not tourist.concerns(national=True)
    assert tourist.concerns(national=False)
    assert local.concerns(national=True)
    assert not local.concerns(national=False)


@pytest.mark.parametrize(
    ("nationality", "doc", "home", "national"),
    [
        ("TN", "PASSPORT", "TN", True),
        ("FR", "CIN", "TN", False),  # the recorded nationality decides
        (None, "CIN", "TN", True),  # a Tunisian identity card without nationality
        (None, "PASSPORT", "TN", False),
        (None, "CIN", "FR", False),  # a CIN means Tunisian, not French
        ("FR", "PASSPORT", "FR", True),
    ],
)
def test_who_is_a_national(nationality, doc, home, national):
    assert is_national(nationality, doc, home) is national


def test_the_taxes_of_a_stay():
    names = lambda rules: [r.name for r in rules]  # noqa: E731
    assert names(taxes_for_stay(_rules(), national=True, exempt_rule_ids=set())) == [
        "VAT",
        "Local levy",
    ]
    assert names(taxes_for_stay(_rules(), national=False, exempt_rule_ids=set())) == [
        "VAT",
        "Tourist tax",
    ]
    assert names(taxes_for_stay(_rules(), national=False, exempt_rule_ids={2})) == ["VAT"]


def test_exemptions_need_a_reason():
    exemption = TaxExemption(id=None, reservation_id=1, tax_rule_id=2, reason="  Diplomat  ")
    exemption.validate()
    assert exemption.reason == "Diplomat"
    with pytest.raises(ValidationError):
        TaxExemption(id=None, reservation_id=1, tax_rule_id=2, reason="   ").validate()
    with pytest.raises(ValidationError):
        TaxExemption(id=None, reservation_id=1, tax_rule_id=2, reason="x" * 201).validate()


def test_the_hotel_country_is_a_real_country():
    assert HotelSettings().home_country == "TN"
    HotelSettings(home_country="FR").validated()
    with pytest.raises(ValidationError) as caught:
        HotelSettings(home_country="XX").validated()
    assert "home_country" in caught.value.fields
    assert HotelSettings.from_strings({"home_country": "MA"}).home_country == "MA"

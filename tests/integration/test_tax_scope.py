"""Taxes by guest and per stay (story 6.16)."""

from dataclasses import replace

import pytest

from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from hotel.domain.guests import GuestDetails
from hotel.domain.money import Money
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxExemption, TaxPayers
from tests.integration.test_booking import book, stay


@pytest.fixture
def taxes(services, hotel):
    settings = services.hotel_settings
    vat = settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    tourist = settings.create_tax_rule(
        hotel.boss,
        PerAdultNightTax(
            name="Tourist tax", amount_per=Money.from_dinars(3), payers=TaxPayers.FOREIGN
        ),
    )
    return vat, tourist


@pytest.fixture
def lucas(services, hotel):
    return services.guests.register(
        hotel.boss, GuestDetails("Lucas", "Dupont", "PASSPORT", "FR1234567", nationality="FR")
    )


def _tax_lines(services, hotel, reservation):
    bill = services.billing.bill(hotel.rita, reservation.id)
    return {line.label: line.amount for line in bill.lines if line.kind == "TAX"}


def test_the_tourist_tax_only_concerns_foreign_guests(services, hotel, taxes, lucas):
    tunisian = book(services, hotel, stay(8, 10), "204", adults=2)  # Amira: CIN, Tunisian
    foreign = book(services, hotel, stay(8, 10), "205", guest=lucas, adults=2)
    assert _tax_lines(services, hotel, tunisian) == {"VAT": Money.from_dinars("25.200")}
    assert _tax_lines(services, hotel, foreign) == {
        "VAT": Money.from_dinars("25.200"),
        "Tourist tax": Money.from_dinars(12),  # 2 adults x 2 nights x 3 DT
    }


def test_the_hotel_country_decides_who_is_national(services, hotel, taxes, lucas):
    settings = services.hotel_settings
    current = settings.get(hotel.boss)
    settings.update(hotel.boss, replace(current, home_country="FR"))
    foreign_now = book(services, hotel, stay(8, 10), "204")  # Amira is foreign in France
    national_now = book(services, hotel, stay(8, 10), "205", guest=lucas)
    assert "Tourist tax" in _tax_lines(services, hotel, foreign_now)
    assert "Tourist tax" not in _tax_lines(services, hotel, national_now)


def test_a_manager_exempts_one_stay_from_one_tax(services, hotel, taxes, lucas, clock):
    _, tourist = taxes
    r = book(services, hotel, stay(8, 10), "205", guest=lucas, adults=2)
    assert [t.name for t in services.billing.exemptible_taxes(hotel.rita, r.id)] == [
        "VAT",
        "Tourist tax",
    ]
    exemption = TaxExemption(
        id=None, reservation_id=r.id, tax_rule_id=tourist.id, reason="Diplomat"
    )
    with pytest.raises(PermissionDeniedError):
        services.billing.exempt_from_tax(hotel.rita, exemption)
    with pytest.raises(ValidationError):
        services.billing.exempt_from_tax(hotel.boss, replace(exemption, reason=""))
    saved = services.billing.exempt_from_tax(hotel.boss, exemption)
    assert "Tourist tax" not in _tax_lines(services, hotel, r)
    assert [e.tax_name for e in services.billing.exemptions(hotel.rita, r.id)] == ["Tourist tax"]
    assert [e.reason for e in services.billing.exemptions(hotel.rita, r.id)] == ["Diplomat"]
    with pytest.raises(ConflictError, match="already_exempt"):
        services.billing.exempt_from_tax(
            hotel.boss,
            TaxExemption(id=None, reservation_id=r.id, tax_rule_id=tourist.id, reason="x"),
        )
    services.billing.remove_exemption(hotel.boss, saved.id)
    assert "Tourist tax" in _tax_lines(services, hotel, r)
    with pytest.raises(NotFoundError):
        services.billing.remove_exemption(hotel.boss, saved.id)
    with services.uow_factory() as uow:
        actions = [e.action for e in uow.audit.iterate()]
    assert "tax.exempted" in actions
    assert "tax.exemption_removed" in actions


def test_the_invoice_follows_the_exemption_and_then_it_is_final(services, hotel, taxes, lucas):
    _, tourist = taxes
    r = book(services, hotel, stay(8, 10), "205", guest=lucas, adults=2)
    services.billing.exempt_from_tax(
        hotel.boss,
        TaxExemption(id=None, reservation_id=r.id, tax_rule_id=tourist.id, reason="Resident"),
    )
    r = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    invoice = services.invoices.check_out(hotel.rita, r.id, version=r.version)
    assert "Tourist tax" not in {line.label for line in invoice.lines}
    exemption_id = services.billing.exemptions(hotel.rita, r.id)[0].id
    with pytest.raises(BusinessRuleViolation, match="bill_closed"):
        services.billing.remove_exemption(hotel.boss, exemption_id)
    with pytest.raises(BusinessRuleViolation, match="bill_closed"):
        services.billing.exempt_from_tax(
            hotel.boss,
            TaxExemption(id=None, reservation_id=r.id, tax_rule_id=taxes[0].id, reason="Late"),
        )


def test_only_active_rules_can_be_exempted(services, hotel, taxes):
    r = book(services, hotel, stay(8, 10), "204")
    with pytest.raises(NotFoundError):
        services.billing.exempt_from_tax(
            hotel.boss, TaxExemption(id=None, reservation_id=r.id, tax_rule_id=999, reason="x")
        )

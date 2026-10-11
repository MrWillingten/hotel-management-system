"""Extra services, charges, hotel settings and tax rules (stories 4.3, 4.8)."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    PermissionDeniedError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.money import Money
from hotel.domain.settings import HotelSettings
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxBase
from tests.integration.test_booking import book, stay


@pytest.fixture
def menu(services, hotel):
    extras = services.extras
    return {
        "breakfast": extras.create(hotel.boss, name="Breakfast", unit_price=Money.from_dinars(15)),
        "transfer": extras.create(
            hotel.boss, name="Airport transfer", unit_price=Money.from_dinars(40)
        ),
    }


def _in_house(services, hotel, period=None, *rooms):
    r = book(services, hotel, period or stay(8, 12), *(rooms or ("204",)))
    return services.reservations.check_in(hotel.rita, r.id, version=r.version)


# ---------------------------------------------------------------- catalogue
def test_catalogue_is_managed_by_managers(services, hotel, menu):
    with pytest.raises(PermissionDeniedError):
        services.extras.create(hotel.rita, name="Spa", unit_price=Money.from_dinars(60))
    with pytest.raises(ConflictError, match="name_taken"):
        services.extras.create(hotel.boss, name="breakfast", unit_price=Money.from_dinars(1))
    names = [e.name for e in services.extras.catalogue(hotel.rita)]
    assert names == ["Airport transfer", "Breakfast"]


def test_deactivated_extras_disappear_from_new_charges_only(services, hotel, menu):
    breakfast = menu["breakfast"]
    updated = services.extras.update(
        hotel.boss,
        breakfast.id,
        version=breakfast.version,
        name="Breakfast",
        unit_price=Money.from_dinars(18),
        is_active=False,
    )
    assert not updated.is_active
    assert [e.name for e in services.extras.catalogue(hotel.rita, active_only=True)] == [
        "Airport transfer"
    ]
    assert len(services.extras.catalogue(hotel.rita)) == 2  # never deleted (BR26)
    with pytest.raises(StaleDataError):
        services.extras.update(
            hotel.boss,
            breakfast.id,
            version=breakfast.version,
            name="Breakfast",
            unit_price=Money.from_dinars(18),
            is_active=True,
        )


# ---------------------------------------------------------------- charges
def test_scenario_4_6_breakfasts_and_an_airport_transfer(services, hotel, menu):
    r = _in_house(services, hotel)  # 4 nights, 8-12 July
    services.extras.charge(hotel.rita, r.id, extra_id=menu["breakfast"].id, quantity=3)
    services.extras.charge(hotel.rita, r.id, extra_id=menu["transfer"].id, quantity=1)
    charges = services.extras.charges_for(hotel.rita, r.id)
    assert [(c.description, c.quantity, c.amount) for c in charges] == [
        ("Breakfast", 3, Money.from_dinars(45)),
        ("Airport transfer", 1, Money.from_dinars(40)),
    ]
    assert all(c.charge_date == date(2026, 7, 8) for c in charges)


def test_the_price_is_copied_when_charged(services, hotel, menu):
    r = _in_house(services, hotel)
    services.extras.charge(hotel.rita, r.id, extra_id=menu["breakfast"].id, quantity=2)
    breakfast = menu["breakfast"]
    services.extras.update(
        hotel.boss,
        breakfast.id,
        version=breakfast.version,
        name="Continental breakfast",
        unit_price=Money.from_dinars(20),
        is_active=True,
    )
    [charge] = services.extras.charges_for(hotel.rita, r.id)
    assert (charge.description, charge.unit_price) == ("Breakfast", Money.from_dinars(15))


def test_charges_need_a_guest_in_the_house(services, hotel, menu):
    r = book(services, hotel, stay(9, 11), "204")
    with pytest.raises(BusinessRuleViolation, match="not_in_house"):
        services.extras.charge(hotel.rita, r.id, extra_id=menu["breakfast"].id, quantity=1)


def test_charges_are_dated_within_the_stay(services, hotel, menu, clock):
    r = _in_house(services, hotel)
    with pytest.raises(ValidationError, match="date_outside_stay"):
        services.extras.charge(
            hotel.rita,
            r.id,
            extra_id=menu["breakfast"].id,
            quantity=1,
            charge_date=date(2026, 7, 9),
        )
    clock.advance(timedelta(days=2))
    charge = services.extras.charge(
        hotel.rita, r.id, extra_id=menu["breakfast"].id, quantity=1, charge_date=date(2026, 7, 9)
    )
    assert charge.charge_date == date(2026, 7, 9)


def test_inactive_or_unknown_extras_cannot_be_charged(services, hotel, menu):
    r = _in_house(services, hotel)
    with pytest.raises(ValidationError, match=r"extra\.unknown"):
        services.extras.charge(hotel.rita, r.id, extra_id=999, quantity=1)


def test_only_managers_void_charges_with_a_reason(services, hotel, menu):
    r = _in_house(services, hotel)
    charge = services.extras.charge(hotel.rita, r.id, extra_id=menu["transfer"].id, quantity=1)
    with pytest.raises(PermissionDeniedError):
        services.extras.void(hotel.rita, charge.id, reason="mistake")
    with pytest.raises(ValidationError):
        services.extras.void(hotel.boss, charge.id, reason=" ")
    voided = services.extras.void(hotel.boss, charge.id, reason="Charged to the wrong room")
    assert voided.is_void
    [stored] = services.extras.charges_for(hotel.rita, r.id)
    assert stored.void_reason == "Charged to the wrong room"  # still visible, never deleted
    with pytest.raises(BusinessRuleViolation, match="already_void"):
        services.extras.void(hotel.boss, charge.id, reason="again")
    with services.uow_factory() as uow:
        assert [e.action for e in uow.audit.iterate()][-1] == "charge.voided"


# ---------------------------------------------------------------- settings
def test_settings_are_manager_only_and_audited(services, hotel):
    assert services.hotel_settings.get(hotel.rita) == HotelSettings()
    new = HotelSettings(check_in_time=time(15, 0), cancellation_fee_bp=5_000)
    with pytest.raises(PermissionDeniedError):
        services.hotel_settings.update(hotel.rita, new)
    services.hotel_settings.update(hotel.boss, new)
    assert services.hotel_settings.get(hotel.rita) == new
    with services.uow_factory() as uow:
        entry = list(uow.audit.iterate())[-1]
    assert entry.action == "settings.updated"
    assert entry.details == {
        "check_in_time": "14:00 -> 15:00",
        "cancellation_fee_bp": "2000 -> 5000",
    }
    with pytest.raises(ValidationError):
        services.hotel_settings.update(hotel.boss, HotelSettings(discount_cap_bp=20_000))


def test_the_cancellation_rule_follows_the_settings(services, hotel):
    r = book(services, hotel, stay(9, 11), "204")  # 360 DT, arrival in 25 hours
    assert services.reservations.cancellation_fee(hotel.rita, r.id) == Money.from_dinars(72)
    services.hotel_settings.update(
        hotel.boss, HotelSettings(cancellation_fee_bp=5_000, cancellation_window_hours=24)
    )
    assert services.reservations.cancellation_fee(hotel.rita, r.id).is_zero()  # outside 24 h
    services.hotel_settings.update(hotel.boss, HotelSettings(cancellation_fee_bp=5_000))
    assert services.reservations.cancellation_fee(hotel.rita, r.id) == Money.from_dinars(180)
    services.hotel_settings.update(hotel.boss, HotelSettings(check_in_time=time(16, 0)))
    free_until = services.reservations.free_cancellation_until(r.period)
    assert free_until == datetime(2026, 7, 7, 15, 0, tzinfo=UTC)  # 16:00 Tunis, 48 h before


# ---------------------------------------------------------------- tax rules
def test_tax_rules(services, hotel):
    vat = services.hotel_settings.create_tax_rule(hotel.boss, PercentTax(name="VAT", rate_bp=700))
    tourist = services.hotel_settings.create_tax_rule(
        hotel.boss, PerAdultNightTax(name="Tourist tax", amount_per=Money.from_dinars(3))
    )
    with pytest.raises(PermissionDeniedError):
        services.hotel_settings.create_tax_rule(hotel.rita, PercentTax(name="X", rate_bp=1))
    with pytest.raises(ValidationError):
        services.hotel_settings.create_tax_rule(
            hotel.boss,
            PerAdultNightTax(name="X", amount_per=Money(1), applies_to=TaxBase.SERVICES),
        )
    rules = services.hotel_settings.tax_rules(hotel.rita)
    assert [(r.name, r.kind) for r in rules] == [
        ("VAT", "PERCENT"),
        ("Tourist tax", "PER_ADULT_NIGHT"),
    ]
    assert rules[1].amount_per == Money(3_000)
    updated = services.hotel_settings.update_tax_rule(
        hotel.boss,
        vat.id,
        PercentTax(name="VAT", rate_bp=900, is_active=False, version=vat.version),
    )
    assert (updated.rate_bp, updated.is_active, updated.version) == (900, False, 2)
    with pytest.raises(StaleDataError):
        services.hotel_settings.update_tax_rule(
            hotel.boss, vat.id, PercentTax(name="VAT", rate_bp=900, version=1)
        )
    assert tourist.id is not None

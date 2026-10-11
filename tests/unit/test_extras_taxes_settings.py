from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from hotel.domain.errors import BusinessRuleViolation, ValidationError
from hotel.domain.extras import (
    ServiceCharge,
    validate_charge,
    validate_extra_name,
    validate_unit_price,
    validate_void_reason,
)
from hotel.domain.money import Money
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import Reservation, ReservationStatus, RoomNight
from hotel.domain.settings import HotelSettings
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxableStay, TaxBase, TaxKind

STAY = StayPeriod(date(2026, 7, 10), date(2026, 7, 14))


def _in_house():
    return Reservation(1, "R-2026-00001", 1, STAY, status=ReservationStatus.CHECKED_IN)


# ---------------------------------------------------------------- extras
def test_extra_names_and_prices():
    assert validate_extra_name("  Airport   transfer ") == "Airport transfer"
    for bad in ("", "x" * 61):
        with pytest.raises(ValidationError):
            validate_extra_name(bad)
    assert validate_unit_price(Money.from_dinars(15)) == Money(15_000)
    for bad in (Money(0), Money.from_dinars(10_001)):
        with pytest.raises(ValidationError):
            validate_unit_price(bad)


def test_charge_amount_is_quantity_times_the_copied_price():
    charge = ServiceCharge(None, 1, 1, "Breakfast", 3, Money.from_dinars(15), date(2026, 7, 11))
    assert charge.amount == Money.from_dinars(45)
    assert not charge.is_void


def test_charges_only_in_the_house_and_within_the_stay():
    today = date(2026, 7, 14)
    validate_charge(_in_house(), date(2026, 7, 10), 1, today)  # arrival day
    validate_charge(_in_house(), date(2026, 7, 14), 99, today)  # departure morning
    with pytest.raises(ValidationError, match="date_outside_stay"):
        validate_charge(_in_house(), date(2026, 7, 9), 1, today)
    with pytest.raises(ValidationError, match="date_outside_stay"):
        validate_charge(_in_house(), date(2026, 7, 12), 1, date(2026, 7, 11))  # future
    with pytest.raises(ValidationError, match="quantity_invalid"):
        validate_charge(_in_house(), date(2026, 7, 10), 100, today)
    confirmed = Reservation(1, "R-2026-00001", 1, STAY)
    with pytest.raises(BusinessRuleViolation, match="not_in_house"):
        validate_charge(confirmed, date(2026, 7, 10), 1, today)


def test_void_reason_is_required():
    assert validate_void_reason("  wrong room ") == "wrong room"
    with pytest.raises(ValidationError):
        validate_void_reason("   ")


# ---------------------------------------------------------------- taxes (Strategy)
STAY_FIGURES = TaxableStay(
    accommodation=Money.from_dinars(450), services=Money.from_dinars(80), adult_nights=6
)


def test_percentage_tax_on_each_base():
    vat = PercentTax(name="VAT", rate_bp=700)
    assert vat.kind is TaxKind.PERCENT
    assert vat.amount(STAY_FIGURES) == Money.from_dinars(Decimal("31.5"))
    on_services = PercentTax(name="VAT", rate_bp=1900, applies_to=TaxBase.SERVICES)
    assert on_services.amount(STAY_FIGURES) == Money(15_200)


def test_percentage_tax_rounds_half_up_to_the_millime():
    vat = PercentTax(name="VAT", rate_bp=700)
    stay = TaxableStay(Money(1_500), Money(0), 0)  # 7 % of 1.500 DT = 0.105
    assert vat.amount(stay) == Money(105)
    stay = TaxableStay(Money(7), Money(0), 0)  # 7 % of 7 millimes = 0.49 -> 0
    assert vat.amount(stay) == Money(0)
    stay = TaxableStay(Money(50), Money(0), 0)  # 3.5 -> 4 (half-up, not banker's 4 either way)
    assert vat.amount(stay) == Money(4)


def test_per_adult_night_tax():
    tourist = PerAdultNightTax(name="Tourist tax", amount_per=Money.from_dinars(3))
    assert tourist.kind is TaxKind.PER_ADULT_NIGHT
    assert tourist.amount(STAY_FIGURES) == Money.from_dinars(18)


def test_tax_validation():
    PercentTax(name=" VAT ", rate_bp=700).validate()
    for rule in (
        PercentTax(name="", rate_bp=700),
        PercentTax(name="VAT", rate_bp=0),
        PercentTax(name="VAT", rate_bp=10_001),
        PerAdultNightTax(name="T", amount_per=Money(0)),
        PerAdultNightTax(name="T", amount_per=Money.from_dinars(1_001)),
        PerAdultNightTax(name="T", amount_per=Money(1), applies_to=TaxBase.SERVICES),
    ):
        with pytest.raises(ValidationError):
            rule.validate()


# ---------------------------------------------------------------- settings
def test_default_settings_are_the_documented_decisions():
    settings = HotelSettings()
    policy = settings.cancellation_policy()
    assert policy.fee_basis_points == 2_000
    assert policy.window == timedelta(hours=48)
    assert policy.check_in_time == time(14, 0)
    assert settings.discount_cap_bp == 3_000


def test_settings_round_trip_through_text_and_ignore_bad_values():
    custom = HotelSettings(check_in_time=time(15, 30), cancellation_fee_bp=1_500)
    assert HotelSettings.from_strings(custom.to_strings()) == custom
    assert (
        HotelSettings.from_strings({"cancellation_fee_bp": "abc", "unknown": "1"})
        == HotelSettings()
    )


def test_settings_validation_names_every_wrong_field():
    with pytest.raises(ValidationError) as caught:
        HotelSettings(cancellation_fee_bp=10_001, grace_period_hours=-1).validated()
    assert set(caught.value.fields) == {"cancellation_fee_bp", "grace_period_hours"}


def test_grace_period_makes_an_early_change_of_mind_free():
    booked = datetime(2026, 7, 9, 8, 0, tzinfo=UTC)  # 30 hours before arrival
    period = StayPeriod(date(2026, 7, 10), date(2026, 7, 11))
    reservation = Reservation(
        1, "R", 1, period, nights=[RoomNight(1, period.arrival, Money(100_000))], created_at=booked
    )
    tunis = ZoneInfo("Africa/Tunis")
    with_grace = HotelSettings(grace_period_hours=2).cancellation_policy()
    assert with_grace.fee_for(reservation, booked + timedelta(hours=1), tunis).is_zero()
    assert with_grace.fee_for(reservation, booked + timedelta(hours=3), tunis) == Money(20_000)
    without = HotelSettings().cancellation_policy()
    assert without.fee_for(reservation, booked + timedelta(hours=1), tunis) == Money(20_000)

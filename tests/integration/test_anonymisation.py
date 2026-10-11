"""Guest anonymisation (story 5.7)."""

from datetime import date, timedelta

import pytest

from hotel.domain.errors import BusinessRuleViolation, PermissionDeniedError
from hotel.domain.guests import months_before
from hotel.domain.paging import PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest
from hotel.domain.settings import HotelSettings
from tests.integration.test_booking import book, stay


@pytest.fixture
def two_years_later(services, hotel, clock):
    """Amira stayed 8-9 July 2026 (invoice issued); Karim registered but never came."""
    r = services.reservations.create(
        hotel.rita,
        guest_id=hotel.amira.id,
        period=stay(8, 9),
        rooms=[RoomRequest(hotel.rooms["204"].id, 1)],
        notes="Allergic to feathers",
    )
    r = services.reservations.check_in(hotel.rita, r.id, version=r.version)
    invoice = services.invoices.check_out(hotel.rita, r.id, version=r.version)
    clock.advance(timedelta(days=760))  # 6 August 2028: cut-off 6 August 2026
    return r, invoice


def test_candidates_have_nothing_since_the_cutoff(services, hotel, two_years_later):
    cutoff, candidates = services.guests.anonymisation_candidates(hotel.boss)
    assert cutoff == date(2026, 8, 6)
    assert {g.full_name for g in candidates} == {"Amira Ben Salah", "Karim Haddad"}
    # A booking for the future protects the guest.
    future = StayPeriod(date(2028, 9, 1), date(2028, 9, 3))
    services.reservations.create(
        hotel.rita,
        guest_id=hotel.karim.id,
        period=future,
        rooms=[RoomRequest(hotel.rooms["101"].id, 1)],
    )
    _, candidates = services.guests.anonymisation_candidates(hotel.boss)
    assert [g.full_name for g in candidates] == ["Amira Ben Salah"]


def test_anonymising_erases_personal_data_but_not_invoices(services, hotel, two_years_later):
    reservation, invoice = two_years_later
    assert services.guests.anonymise(hotel.boss, [hotel.amira.id]) == 1
    guest = services.guests.get(hotel.boss, hotel.amira.id)
    assert guest.full_name == "Anonymised guest"
    assert guest.id_doc_number.startswith("ANON-")
    assert (guest.phone, guest.email, guest.nationality, guest.notes) == (None, None, None, "")
    assert guest.is_anonymised
    assert services.reservations.get(hotel.boss, reservation.id).notes == ""
    assert services.invoices.get(hotel.boss, invoice.id).guest_name == "Amira Ben Salah"
    assert services.guests.search(hotel.boss, "amira", PageRequest()).total == 0
    with services.uow_factory() as uow:
        entry = list(uow.audit.iterate())[-1]
    assert entry.action == "guest.anonymised"
    assert "Amira" not in entry.canonical()
    with pytest.raises(BusinessRuleViolation, match="anonymised"):  # never booked again
        book(services, hotel, StayPeriod(date(2028, 9, 1), date(2028, 9, 2)), "205")
    with pytest.raises(BusinessRuleViolation, match="anonymised"):  # nor edited
        services.guests.set_flags(
            hotel.boss, guest.id, version=guest.version, is_vip=True, do_not_rent=False
        )


def test_anonymisation_rules(services, hotel, two_years_later):
    with pytest.raises(PermissionDeniedError):
        services.guests.anonymise(hotel.rita, [hotel.amira.id])
    services.guests.anonymise(hotel.boss, [hotel.amira.id])
    with pytest.raises(BusinessRuleViolation, match="not_anonymisable"):
        services.guests.anonymise(hotel.boss, [hotel.amira.id])  # already done


def test_recent_guests_are_not_proposed(services, hotel):
    services.hotel_settings.update(hotel.boss, HotelSettings(anonymise_after_months=6))
    _, candidates = services.guests.anonymisation_candidates(hotel.boss)
    assert candidates == []
    with pytest.raises(BusinessRuleViolation):
        services.guests.anonymise(hotel.boss, [hotel.karim.id])


def test_months_before_clamps_to_shorter_months():
    assert months_before(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert months_before(date(2024, 3, 31), 1) == date(2024, 2, 29)
    assert months_before(date(2026, 7, 8), 24) == date(2024, 7, 8)

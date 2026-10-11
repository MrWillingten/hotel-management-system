import pytest

from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from hotel.domain.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.guests import GuestDetails
from hotel.domain.paging import PageRequest
from hotel.services.guests import ProbableDuplicateError

TEMP = "temporary-pass-4521"

AMIRA = GuestDetails(
    "Amira",
    "Ben Salah",
    "CIN",
    "09123456",
    "TN",
    "+216 20 123 456",
    "amira@example.tn",
    "Prefers a quiet room",
)


@pytest.fixture
def boss(manager):
    return Actor(manager)


@pytest.fixture
def rita(services, boss):
    user = services.users.create_user(
        boss,
        username="rita",
        full_name="Rita",
        role=Role.RECEPTIONIST,
        temporary_password=TEMP,
    )
    return Actor(user)


@pytest.fixture
def amira(services, rita, manager):
    return services.guests.register(rita, AMIRA)


def _audit(services):
    with services.uow_factory() as uow:
        return list(uow.audit.iterate())


def test_register_and_get(services, rita, amira):
    assert amira.id is not None
    assert amira.phone == "+21620123456"
    assert services.guests.get(rita, amira.id).full_name == "Amira Ben Salah"
    entry = _audit(services)[-1]
    assert entry.action == "guest.created"
    # No personal data in the audit trail.
    assert "Amira" not in entry.canonical()
    assert "09123456" not in entry.canonical()


def test_same_document_is_refused(services, rita, amira):
    twin = GuestDetails("Someone", "Else", "CIN", "0912-3456")
    with pytest.raises(ConflictError) as caught:
        services.guests.register(rita, twin, confirm_duplicate=True)
    assert caught.value.code == "guest.document_taken"
    assert caught.value.params == {"existing_id": amira.id}


def test_scenario_4_2_returning_guest_is_flagged(services, rita, amira):
    """Same name and phone, different passport: probably the same person."""
    returning = GuestDetails("amira", "BEN SALAH", "PASSPORT", "TN998877", phone="20123456")
    returning_with_code = GuestDetails(
        "Amira", "Ben Salah", "PASSPORT", "TN112233", phone="+216 20 123 456"
    )
    services.guests.register(rita, returning)  # different digits: not flagged
    with pytest.raises(ProbableDuplicateError) as caught:
        services.guests.register(
            rita,
            GuestDetails("Amira", "Ben Salah", "PASSPORT", "ZZ55555", email="AMIRA@example.tn"),
        )
    assert [g.id for g in caught.value.candidates] == [amira.id]
    with pytest.raises(ProbableDuplicateError):
        services.guests.register(rita, returning_with_code)
    confirmed = services.guests.register(
        rita,
        GuestDetails("Amira", "Ben Salah", "PASSPORT", "ZZ55555", email="amira@example.tn"),
        confirm_duplicate=True,
    )
    assert _audit(services)[-1].details["confirmed_duplicate"] is True
    assert confirmed.id != amira.id


def test_update_keeps_the_record_and_checks_versions(services, rita, amira):
    """Scenario §4.1 (students) / §4.2: a guest changes e-mail; history is untouched."""
    new = GuestDetails(
        "Amira", "Ben Salah", "CIN", "09123456", "TN", "+216 20 123 456", "amira.bs@example.tn", ""
    )
    updated = services.guests.update(rita, amira.id, version=amira.version, details=new)
    assert updated.id == amira.id
    assert updated.email == "amira.bs@example.tn"
    assert _audit(services)[-1].details["fields"] == ["email", "notes"]
    with pytest.raises(StaleDataError):
        services.guests.update(rita, amira.id, version=amira.version, details=new)


def test_update_cannot_steal_another_document(services, rita, amira):
    other = services.guests.register(rita, GuestDetails("Karim", "Haddad", "CIN", "11112222"))
    steal = GuestDetails("Karim", "Haddad", "CIN", "09123456")
    with pytest.raises(ConflictError, match="document_taken"):
        services.guests.update(rita, other.id, version=other.version, details=steal)


def test_flags(services, rita, boss, amira):
    vip = services.guests.set_flags(
        rita, amira.id, version=amira.version, is_vip=True, do_not_rent=False
    )
    assert vip.is_vip
    with pytest.raises(PermissionDeniedError):
        services.guests.set_flags(
            rita, amira.id, version=vip.version, is_vip=True, do_not_rent=True, reason="Damage"
        )
    with pytest.raises(ValidationError, match="reason_required"):
        services.guests.set_flags(
            boss, amira.id, version=vip.version, is_vip=True, do_not_rent=True, reason="  "
        )
    banned = services.guests.set_flags(
        boss, amira.id, version=vip.version, is_vip=False, do_not_rent=True, reason="Unpaid  bill"
    )
    assert banned.do_not_rent_reason == "Unpaid bill"
    # A receptionist can still change VIP status without touching do-not-rent.
    kept = services.guests.set_flags(
        rita, amira.id, version=banned.version, is_vip=True, do_not_rent=True, reason="Unpaid bill"
    )
    assert kept.do_not_rent
    assert kept.is_vip
    with pytest.raises(PermissionDeniedError):
        services.guests.set_flags(
            rita, amira.id, version=kept.version, is_vip=True, do_not_rent=False
        )
    cleared = services.guests.set_flags(
        boss, amira.id, version=kept.version, is_vip=True, do_not_rent=False, reason="ignored"
    )
    assert cleared.do_not_rent_reason is None


def test_reveal_document_is_audited(services, rita, amira):
    assert services.guests.reveal_document(rita, amira.id) == "09123456"
    entry = _audit(services)[-1]
    assert (entry.action, entry.username, entry.entity_id) == (
        "guest.document_revealed",
        "rita",
        str(amira.id),
    )


def test_missing_guest(services, rita):
    with pytest.raises(NotFoundError):
        services.guests.get(rita, 404)


@pytest.fixture
def directory(services, rita, manager):
    people = [
        ("Amira", "Ben Salah", "CIN", "09123456", "+216 20 123 456", "amira@example.tn"),
        ("Hélène", "Dupont", "PASSPORT", "FR778899", "+33 6 12 34 56 78", ""),
        ("Karim", "Haddad", "CIN", "11112222", "", "karim_h@example.com"),
        ("Sami", "Ben Ali", "CIN", "33334444", "98 765 432", ""),
    ]
    for first, last, doc_type, number, phone, email in people:
        services.guests.register(
            rita, GuestDetails(first, last, doc_type, number, "", phone, email)
        )


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["Ben Ali", "Ben Salah", "Dupont", "Haddad"]),
        ("helene", ["Dupont"]),  # accent-insensitive
        ("BEN", ["Ben Ali", "Ben Salah"]),
        ("ben sal", ["Ben Salah"]),  # every word must match
        ("0912", ["Ben Salah"]),  # document number prefix
        ("765 432", ["Ben Ali"]),  # phone digits
        ("karim_h", ["Haddad"]),  # e-mail
        ("%", []),  # LIKE wildcards are literal
        ("_", ["Haddad"]),  # only karim_h@ contains an underscore
        ("' OR 1=1 --", []),  # injection attempt is just text
    ],
)
def test_search(services, rita, directory, query, expected):
    page = services.guests.search(rita, query, PageRequest())
    assert [g.last_name for g in page.items] == expected


def test_search_sorting_and_paging(services, rita, directory):
    newest = services.guests.search(rita, "", PageRequest(per_page=3), sort="newest")
    assert [g.last_name for g in newest.items] == ["Ben Ali", "Haddad", "Dupont"]
    assert (newest.total, newest.pages, newest.has_next) == (4, 2, True)
    second = services.guests.search(rita, "", PageRequest(page=2, per_page=3), sort="oldest")
    assert [g.last_name for g in second.items] == ["Ben Ali"]
    unknown = services.guests.search(rita, "", PageRequest(), sort="id; DROP TABLE guest")
    assert unknown.total == 4  # unknown sort keys fall back to the default

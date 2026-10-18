import pytest

from hotel.domain.errors import ValidationError
from hotel.domain.guests import (
    Guest,
    GuestDetails,
    IdDocType,
    normalize_country,
    normalize_doc_number,
    normalize_email,
    normalize_phone,
    search_key,
    validate_name,
)


def test_search_key_ignores_case_and_accents():
    assert search_key("  Hélène   ÇELİK ") == "helene celik"
    assert search_key("Ben Saâd") == "ben saad"


@pytest.mark.parametrize(
    "name", ["Amira", "Ben Salah", "O'Brien", "Jean-Luc", "أمينة", "D. Dupont"]
)
def test_valid_names(name):
    assert validate_name(f"  {name} ", "first_name") == name


@pytest.mark.parametrize("name", ["", "   ", "R2D2", "<script>", "x" * 61, "Ali;--"])
def test_invalid_names(name):
    with pytest.raises(ValidationError) as caught:
        validate_name(name, "last_name")
    assert caught.value.fields == {"last_name": "guest.name_invalid"}


def test_documents():
    assert normalize_doc_number(IdDocType.CIN, " 0912 3456 ") == "09123456"
    assert normalize_doc_number(IdDocType.PASSPORT, "x-12.345/6") == "X123456"
    assert normalize_doc_number(IdDocType.PASSPORT, "ab 1234567") == "AB1234567"
    assert normalize_doc_number(IdDocType.PASSPORT, "123456789") == "123456789"  # e.g. US
    for bad in ("1234567", "123456789", "ABCDEFGH"):
        with pytest.raises(ValidationError, match="cin_invalid"):
            normalize_doc_number(IdDocType.CIN, bad)


@pytest.mark.parametrize(
    "bad",
    [
        "AB1",  # too short
        "ABCDEFG",  # letters only: not a passport number
        "A1234567890",  # longer than the 9 characters of ICAO 9303
        "AB12345!",  # symbols
        "AB 12345É",  # accented letters
    ],
)
def test_invalid_passports(bad):
    with pytest.raises(ValidationError, match="passport_invalid"):
        normalize_doc_number(IdDocType.PASSPORT, bad)


@pytest.mark.parametrize(
    ("raw", "phone"),
    [
        ("20 123 456", "+21620123456"),  # without a code: Tunisian
        ("+216 20-123-456", "+21620123456"),
        ("00 33 6 12 34 56 78", "+33612345678"),  # 00 works like +
        ("(71) 123.456", "+21671123456"),  # Tunis landline
        ("+1 202-555-0143", "+12025550143"),
        ("", None),
    ],
)
def test_phones(raw, phone):
    assert normalize_phone(raw) == phone


@pytest.mark.parametrize(
    "raw",
    [
        "123",
        "call me",
        "+1 234 567 890 123 456",
        "20 12x 456",
        "12 345 678",  # no Tunisian number starts with 1
        "2012345",  # 7 digits
        "+33 1",  # France, far too short
        "+999 12345678",  # no such country code
    ],
)
def test_invalid_phones(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)


def test_emails_and_countries():
    assert normalize_email(" Amira@Example.TN ") == "amira@example.tn"
    assert normalize_email("") is None
    assert normalize_email("first.last+hotel@mail.example.co.uk") == (
        "first.last+hotel@mail.example.co.uk"
    )
    assert normalize_email("amira@café.tn") == "amira@xn--caf-dma.tn"  # ASCII form for mail servers
    bad_emails = (
        "amira",
        "a@b",
        "a b@c.d",
        "x" * 250 + "@a.tn",
        "a..b@example.tn",  # double dot
        ".a@example.tn",
        "a@example..tn",
        "a@-example.tn",  # label starting with a hyphen
        "a@example.t",  # one-letter top-level domain
        "a@example.123",
        "a@@example.tn",
        "x" * 65 + "@example.tn",  # local part over 64
    )
    for bad in bad_emails:
        with pytest.raises(ValidationError):
            normalize_email(bad)
    assert normalize_country("tn") == "TN"
    assert normalize_country("") is None
    for bad in ("TUN", "ZZ", "EU", "Tunisia"):
        with pytest.raises(ValidationError):
            normalize_country(bad)


def test_details_are_cleaned_together():
    details = GuestDetails("amira", "ben salah", "CIN", "0912 3456", "tn", "20 123 456", "", "  ")
    cleaned = details.cleaned()
    assert cleaned.id_doc_number == "09123456"
    assert cleaned.nationality == "TN"
    assert cleaned.notes == ""
    with pytest.raises(ValidationError, match="doc_type_invalid"):
        GuestDetails("A", "B", "DRIVING", "123").cleaned()
    with pytest.raises(ValidationError, match="notes"):
        GuestDetails("A", "B", "CIN", "12345678", notes="x" * 501).cleaned()


def test_guest_helpers_and_apply():
    guest = Guest(None, "", "", IdDocType.CIN, "")
    changed = guest.apply(GuestDetails("Hélène", "Dupont", "PASSPORT", "AB12345").cleaned())
    assert {"first_name", "id_doc_type"} <= set(changed)
    assert guest.full_name == "Hélène Dupont"
    assert guest.search_name == "helene dupont"
    assert guest.sort_name == "dupont helene"
    assert guest.masked_doc_number == "••••345"
    assert guest.phone_digits is None
    assert guest.apply(GuestDetails("Hélène", "Dupont", "PASSPORT", "AB12345").cleaned()) == []


def test_every_problem_is_reported_at_once():
    with pytest.raises(ValidationError) as caught:
        GuestDetails("R2", "", "CIN", "12", "TUN", "abc", "nope").cleaned()
    assert set(caught.value.fields) == {
        "first_name",
        "last_name",
        "id_doc_number",
        "nationality",
        "phone",
        "email",
    }

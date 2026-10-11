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
    for bad in ("1234567", "123456789", "ABCDEFGH"):
        with pytest.raises(ValidationError, match="cin_invalid"):
            normalize_doc_number(IdDocType.CIN, bad)
    with pytest.raises(ValidationError, match="passport_invalid"):
        normalize_doc_number(IdDocType.PASSPORT, "AB1")


@pytest.mark.parametrize(
    ("raw", "phone"),
    [
        ("20 123 456", "20123456"),
        ("+216 20-123-456", "+21620123456"),
        ("00 33 6 12 34 56 78", "+33612345678"),
        ("(71) 123.456", "71123456"),
        ("", None),
    ],
)
def test_phones(raw, phone):
    assert normalize_phone(raw) == phone


@pytest.mark.parametrize("raw", ["123", "call me", "+1 234 567 890 123 456", "20 12x 456"])
def test_invalid_phones(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)


def test_emails_and_countries():
    assert normalize_email(" Amira@Example.TN ") == "amira@example.tn"
    assert normalize_email("") is None
    for bad in ("amira", "a@b", "a b@c.d", "x" * 250 + "@a.tn"):
        with pytest.raises(ValidationError):
            normalize_email(bad)
    assert normalize_country("tn") == "TN"
    assert normalize_country("") is None
    with pytest.raises(ValidationError):
        normalize_country("TUN")


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

"""Guests and their identity documents."""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

import phonenumbers

from hotel.domain.errors import ValidationError

MAX_NAME = 60
MAX_NOTES = 500
_NAME_PUNCTUATION = frozenset(" -'’.")
_CIN = re.compile(r"^\d{8}$")  # Tunisian national identity card: 8 digits
# Passport numbers (ICAO 9303): at most 9 letters and digits. Real ones always
# contain digits, so a word such as "ABCDEFG" is a typing mistake, not a passport.
_PASSPORT = re.compile(r"^(?=.*\d)[A-Z0-9]{6,9}$")
# E-mail: a practical subset of RFC 5321, the addresses people really use.
_EMAIL_LOCAL = re.compile(r"^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")
_DOMAIN_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_TLD = re.compile(r"^([a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
# Phone numbers typed without a country code are Tunisian (the hotel's country).
HOME_REGION = "TN"
# Countries a guest can come from: every region Google's phone-number data knows
# (ISO 3166-1 alpha-2 codes, 245 of them), so nationality and phone agree.
COUNTRY_CODES = frozenset(phonenumbers.SUPPORTED_REGIONS)


class IdDocType(StrEnum):
    CIN = "CIN"
    PASSPORT = "PASSPORT"


def search_key(text: str) -> str:
    """Lower-case and without accents, so "Hélène" is found by typing "helene"."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


def _invalid(field: str, code: str, **params) -> ValidationError:
    return ValidationError(code, fields={field: code}, **params)


def validate_name(raw: str, field: str) -> str:
    name = " ".join(unicodedata.normalize("NFC", raw).split())
    if not 1 <= len(name) <= MAX_NAME:
        raise _invalid(field, "guest.name_invalid", max_length=MAX_NAME)
    if not all(c.isalpha() or c in _NAME_PUNCTUATION for c in name):
        raise _invalid(field, "guest.name_invalid", max_length=MAX_NAME)
    return name


def normalize_doc_number(doc_type: IdDocType, raw: str) -> str:
    number = re.sub(r"[\s\-./]", "", unicodedata.normalize("NFKC", raw)).upper()
    pattern = _CIN if doc_type is IdDocType.CIN else _PASSPORT
    if not pattern.fullmatch(number):
        code = "guest.cin_invalid" if doc_type is IdDocType.CIN else "guest.passport_invalid"
        raise _invalid("id_doc_number", code)
    return number


def normalize_phone(raw: str) -> str | None:
    """A real, dialable number, stored in E.164 form ("+21620123456").

    Google's libphonenumber knows, for every country, which lengths and
    prefixes exist (mobile, landline...). A number without a country code is
    read as Tunisian; "00" works like "+". Letters and impossible numbers
    (wrong length, unused prefix) are refused.
    """
    text = unicodedata.normalize("NFKC", raw).strip()
    if not text:
        return None
    if re.search(r"[^\d\s\-.()+/]", text):  # no letters: "0800-HOTEL" is not stored
        raise _invalid("phone", "guest.phone_invalid")
    try:
        number = phonenumbers.parse(text, HOME_REGION)
    except phonenumbers.NumberParseException:
        raise _invalid("phone", "guest.phone_invalid") from None
    if not phonenumbers.is_valid_number(number):
        raise _invalid("phone", "guest.phone_invalid")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def display_phone(stored: str | None) -> str:
    """ "+21620123456" -> "+216 20 123 456"; anything unreadable is shown as stored."""
    if not stored:
        return ""
    try:
        number = phonenumbers.parse(stored, HOME_REGION)
    except phonenumbers.NumberParseException:
        return stored
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


def normalize_email(raw: str) -> str | None:
    """Checked part by part: "name@domain.tld", no spaces, no double dots.

    International domain names ("café.tn") are stored in their ASCII form
    ("xn--caf-dma.tn"), which is what mail servers use.
    """
    email = unicodedata.normalize("NFKC", raw).strip().lower()
    if not email:
        return None
    local, at, domain = email.rpartition("@")
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        raise _invalid("email", "guest.email_invalid") from None
    labels = domain.split(".")
    email = f"{local}@{domain}"
    if (
        not at
        or len(email) > 254
        or not 1 <= len(local) <= 64
        or not _EMAIL_LOCAL.fullmatch(local)
        or len(labels) < 2
        or not all(_DOMAIN_LABEL.fullmatch(label) for label in labels)
        or not _TLD.fullmatch(labels[-1])
    ):
        raise _invalid("email", "guest.email_invalid")
    return email


def normalize_country(raw: str) -> str | None:
    """An ISO 3166-1 alpha-2 code of a real country ("TN", "FR")."""
    code = raw.strip().upper()
    if not code:
        return None
    if code not in COUNTRY_CODES:
        raise _invalid("nationality", "guest.nationality_invalid")
    return code


@dataclass(frozen=True, slots=True)
class GuestDetails:
    """What a receptionist types; validated and normalised by `cleaned()`."""

    first_name: str
    last_name: str
    id_doc_type: str
    id_doc_number: str
    nationality: str = ""
    phone: str = ""
    email: str = ""
    notes: str = ""

    def cleaned(self) -> GuestDetails:
        """Validate every field and report *all* problems at once, not just the first."""
        problems: dict[str, str] = {}
        params: dict[str, object] = {}

        def check(func, *args):
            try:
                return func(*args)
            except ValidationError as error:
                problems.update(error.fields)
                params.update(error.params)
                return ""

        try:
            doc_type: IdDocType | None = IdDocType(self.id_doc_type)
        except ValueError:
            doc_type = None
            problems["id_doc_type"] = "guest.doc_type_invalid"
        notes = unicodedata.normalize("NFC", self.notes).strip()
        if len(notes) > MAX_NOTES:
            problems["notes"] = "notes.invalid"
            params["max_length"] = MAX_NOTES
        cleaned = GuestDetails(
            first_name=check(validate_name, self.first_name, "first_name"),
            last_name=check(validate_name, self.last_name, "last_name"),
            id_doc_type=doc_type.value if doc_type else "",
            id_doc_number=check(normalize_doc_number, doc_type, self.id_doc_number)
            if doc_type
            else "",
            nationality=check(normalize_country, self.nationality) or "",
            phone=check(normalize_phone, self.phone) or "",
            email=check(normalize_email, self.email) or "",
            notes=notes,
        )
        if problems:
            raise ValidationError(next(iter(problems.values())), fields=problems, **params)
        return cleaned


@dataclass(slots=True)
class Guest:
    id: int | None
    first_name: str
    last_name: str
    id_doc_type: IdDocType
    id_doc_number: str
    nationality: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str = ""
    is_vip: bool = False
    do_not_rent: bool = False
    do_not_rent_reason: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    version: int = 1
    anonymised_at: datetime | None = None

    @property
    def is_anonymised(self) -> bool:
        return self.anonymised_at is not None

    def anonymise(self, now: datetime) -> None:
        """Story 5.7: erase the personal data, keep the record (BR26) and its history.

        The name becomes "Anonymised guest", the identity document a placeholder
        that stays unique (BR2: type + number), and every contact detail and
        note is removed. Invoices are untouched: they hold their own copy of the
        name, as accounting records must. The record stays visible (its past
        reservations still link to it) but can no longer be booked or edited.
        """
        self.first_name, self.last_name = "Anonymised", "guest"
        self.id_doc_number = f"ANON-{self.id:06d}"
        self.nationality = self.phone = self.email = None
        self.notes = ""
        self.is_vip = self.do_not_rent = False
        self.do_not_rent_reason = None
        self.anonymised_at = now

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def search_name(self) -> str:
        return search_key(self.full_name)

    @property
    def sort_name(self) -> str:
        return search_key(f"{self.last_name} {self.first_name}")

    @property
    def phone_digits(self) -> str | None:
        return re.sub(r"\D", "", self.phone) if self.phone else None

    @property
    def masked_doc_number(self) -> str:
        """Only the last 3 characters are shown until someone asks (and is audited)."""
        return "•" * 4 + self.id_doc_number[-3:]

    def apply(self, details: GuestDetails) -> list[str]:
        """Copy cleaned details onto the guest; return the names of changed fields."""
        new = {
            "first_name": details.first_name,
            "last_name": details.last_name,
            "id_doc_type": IdDocType(details.id_doc_type),
            "id_doc_number": details.id_doc_number,
            "nationality": details.nationality or None,
            "phone": details.phone or None,
            "email": details.email or None,
            "notes": details.notes,
        }
        changed = [name for name, value in new.items() if getattr(self, name) != value]
        for name, value in new.items():
            setattr(self, name, value)
        return changed


def months_before(day: date, months: int) -> date:
    """The same day `months` earlier, clamped to the end of shorter months (31 May - 3 = 28 Feb)."""
    year, month_index = divmod(day.year * 12 + (day.month - 1) - months, 12)
    month = month_index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))

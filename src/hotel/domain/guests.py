"""Guests and their identity documents."""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from hotel.domain.errors import ValidationError

MAX_NAME = 60
MAX_NOTES = 500
_NAME_PUNCTUATION = frozenset(" -'’.")
_CIN = re.compile(r"^\d{8}$")  # Tunisian national identity card: 8 digits
_PASSPORT = re.compile(r"^[A-Z0-9]{5,20}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")


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
    text = unicodedata.normalize("NFKC", raw).strip()
    if not text:
        return None
    plus = text.startswith("+") or text.startswith("00")
    digits = re.sub(r"\D", "", text)
    if text.startswith("00"):
        digits = digits[2:]
    if re.sub(r"[\d\s\-.()+]", "", text) or not 8 <= len(digits) <= 15:
        raise _invalid("phone", "guest.phone_invalid")
    return ("+" if plus else "") + digits


def normalize_email(raw: str) -> str | None:
    email = unicodedata.normalize("NFKC", raw).strip().lower()
    if not email:
        return None
    if len(email) > 254 or not _EMAIL.fullmatch(email):
        raise _invalid("email", "guest.email_invalid")
    return email


def normalize_country(raw: str) -> str | None:
    code = raw.strip().upper()
    if not code:
        return None
    if not _COUNTRY.fullmatch(code):
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

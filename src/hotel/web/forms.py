"""Reading user input from requests into typed values.

This is the *shape* check (is it a number? a date?). Business rules are checked
again by the domain and services, which never trust the web layer.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import date, time

from hotel.domain.errors import HotelError, ValidationError
from hotel.domain.money import Money
from hotel.domain.paging import PageRequest
from hotel.web.messages import message_for


class FormErrors(dict[str, str]):
    """Field name -> translated message, filled from a ValidationError."""

    @classmethod
    def from_error(cls, error: HotelError) -> FormErrors:
        errors = cls()
        for field, code in error.fields.items():
            errors[field] = message_for(code, error.params)
        if not errors:
            errors["__all__"] = message_for(error.code, error.params)
        return errors


def text(data: Mapping[str, str], name: str, *, max_length: int = 200) -> str:
    """Trimmed, NFC-normalised text, cut to a sane maximum length."""
    value = unicodedata.normalize("NFC", data.get(name, "")).strip()
    return value[:max_length]


def optional_text(data: Mapping[str, str], name: str, *, max_length: int = 200) -> str | None:
    return text(data, name, max_length=max_length) or None


def integer(data: Mapping[str, str], name: str, *, required: bool = True) -> int | None:
    raw = data.get(name, "").strip()
    if not raw and not required:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ValidationError("field.not_a_number", fields={name: "field.not_a_number"}) from None


def checkbox(data: Mapping[str, str], name: str) -> bool:
    return data.get(name) in {"on", "1", "true", "yes"}


def calendar_date(data: Mapping[str, str], name: str, *, required: bool = True) -> date | None:
    raw = data.get(name, "").strip()
    if not raw and not required:
        return None
    try:
        return date.fromisoformat(raw)  # <input type="date"> always sends YYYY-MM-DD
    except ValueError:
        raise ValidationError("field.invalid_date", fields={name: "field.invalid_date"}) from None


def money(data: Mapping[str, str], name: str) -> Money:
    """Accept "180", "180.5" or, as French users type it, "180,5".

    Thousands separators are not accepted, so "1,500" always means 1.5 DT and
    can never be silently read as 1500 DT.
    """
    raw = data.get(name, "").strip().replace(" ", "").replace(" ", "")
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    try:
        return Money.parse(raw)
    except ValidationError as error:
        raise ValidationError(error.code, fields={name: error.code}, **error.params) from None


_PERCENT = re.compile(r"^(\d{1,3})(?:[.,](\d{1,2}))?$")


def percent(data: Mapping[str, str], name: str) -> int:
    """ "20" -> 2000 basis points, "7.5" or "7,5" -> 750. Two decimals at most."""
    match = _PERCENT.fullmatch(data.get(name, "").strip().removesuffix("%").strip())
    if match is None or int(match.group(1)) > 100:
        raise ValidationError("field.invalid_percent", fields={name: "field.invalid_percent"})
    return int(match.group(1)) * 100 + int((match.group(2) or "").ljust(2, "0"))


def clock_time(data: Mapping[str, str], name: str) -> time:
    raw = data.get(name, "").strip()
    try:
        return time.fromisoformat(raw).replace(second=0, microsecond=0)  # <input type="time">
    except ValueError:
        raise ValidationError("field.invalid_time", fields={name: "field.invalid_time"}) from None


def page_request(args: Mapping[str, str], *, per_page: int = 20) -> PageRequest:
    try:
        page = int(args.get("page", "1"))
    except ValueError:
        page = 1
    return PageRequest(page=page, per_page=per_page)

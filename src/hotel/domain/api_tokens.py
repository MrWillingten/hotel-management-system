"""Personal access tokens for the read-only JSON API (story 6.3).

A token is a long random string a manager gives to another program (a
spreadsheet, a dashboard). It acts as that manager, but the API can only
read. It is shown once; the database keeps its SHA-256 hash, so a stolen
copy of the database contains no usable token.
"""

from __future__ import annotations

import secrets
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from hotel.domain.errors import ValidationError

# A recognisable start makes leaked tokens easy to spot (e.g. by secret scanners).
MARKER = "hotel_"
LIFETIMES = (30, 90, 365)  # days a manager may choose from
MAX_ACTIVE_PER_USER = 10


def new_token() -> str:
    return MARKER + secrets.token_urlsafe(32)  # 256 bits of randomness


def validate_name(raw: str) -> str:
    name = " ".join(unicodedata.normalize("NFC", raw).split())
    if not 1 <= len(name) <= 60:
        raise ValidationError("api_token.name_invalid", fields={"name": "api_token.name_invalid"})
    return name


def validate_lifetime(days: int) -> timedelta:
    if days not in LIFETIMES:
        raise ValidationError(
            "api_token.lifetime_invalid", fields={"days": "api_token.lifetime_invalid"}
        )
    return timedelta(days=days)


@dataclass(slots=True)
class ApiToken:
    id: int | None
    user_id: int
    name: str
    token_hash: str
    prefix: str  # e.g. "hotel_Ab3d": enough to recognise, useless to sign in
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_valid(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at

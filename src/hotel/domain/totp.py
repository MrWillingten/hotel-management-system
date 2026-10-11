"""Time-based one-time passwords, the second factor of a manager's sign-in (story 6.1).

TOTP (RFC 6238) is HOTP (RFC 4226) fed with the number of 30-second steps
since 1970. The phone and the server share a random secret; both compute
HMAC-SHA1(secret, step), cut it down to six digits, and compare. Nothing
travels over the network except the six digits, which expire quickly.

Written with the standard library only (hmac, hashlib, base64) so every line
can be explained; the result is checked against the RFC's own test vectors
in tests/unit/test_totp.py.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from hotel.domain.errors import ValidationError

STEP_SECONDS = 30
DIGITS = 6
# A code from the previous or the next step is accepted too: phones' clocks
# drift and people need a few seconds to type. Wider windows help guessing.
DRIFT_STEPS = 1
SECRET_BYTES = 20  # 160 bits, the length RFC 4226 recommends for SHA-1
GRACE = timedelta(days=7)  # managers must enrol within a week (decision 11 Oct)

RECOVERY_CODES = 10
# Recovery codes avoid letters that look alike (0/O, 1/I/L). 12 characters
# from 30 symbols give about 59 bits: far beyond online guessing, which the
# account lockout limits to a handful of attempts anyway.
_RECOVERY_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_RECOVERY_LENGTH = 12


# ---------------------------------------------------------------- the algorithm
def new_secret() -> str:
    """A random shared secret in base32, the form authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def hotp(secret: str, counter: int, *, digits: int = DIGITS) -> str:
    """RFC 4226: HMAC-SHA1 of the counter, "dynamic truncation", then the last digits."""
    mac = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F  # the last 4 bits choose where to read 4 bytes
    number = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**digits).zfill(digits)


def time_step(now: datetime) -> int:
    return int(now.timestamp()) // STEP_SECONDS


def totp(secret: str, now: datetime) -> str:
    return hotp(secret, time_step(now))


def normalize_code(raw: str) -> str:
    """Users may type "123 456"; keep the digits only (or the code for a recovery code)."""
    return "".join(raw.split()).replace("-", "").upper()


def matching_step(secret: str, code: str, now: datetime, *, last_used: int | None) -> int | None:
    """The time step the code belongs to, or None if it is wrong or already used.

    A code is refused if its step is not *after* the last accepted one: an
    attacker who watched the screen or the network cannot replay it within
    its 90-second lifetime (threat A11).
    """
    code = normalize_code(code)
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = time_step(now)
    for step in range(current - DRIFT_STEPS, current + DRIFT_STEPS + 1):
        if last_used is not None and step <= last_used:
            continue
        # compare_digest takes the same time whether the first digit or the last one differs.
        if hmac.compare_digest(hotp(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, *, account: str, issuer: str) -> str:
    """The otpauth:// link the QR code contains (Google Authenticator's key URI format)."""
    label = quote(f"{issuer}:{account}", safe=":@")
    query = urlencode(
        {"secret": secret, "issuer": issuer, "digits": DIGITS, "period": STEP_SECONDS}
    )
    return f"otpauth://totp/{label}?{query}"


def grouped(secret: str) -> str:
    """The secret in blocks of four, easier to type when the QR code cannot be scanned."""
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))


# ---------------------------------------------------------------- recovery codes
def new_recovery_codes(count: int = RECOVERY_CODES) -> list[str]:
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_LENGTH))
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:]}")
    return codes


def hash_recovery_code(code: str) -> str:
    """Stored hashed like session tokens: the codes are random, so SHA-256 is enough."""
    return hashlib.sha256(normalize_code(code).encode("ascii", "replace")).hexdigest()


def looks_like_recovery_code(code: str) -> bool:
    return len(normalize_code(code)) == _RECOVERY_LENGTH


# ---------------------------------------------------------------- the account's state
@dataclass(slots=True)
class TwoFactor:
    """A user's second-factor state, stored with the account.

    `pending_secret` is set while the user enrols: it becomes `secret` only
    after they typed one correct code, which proves their phone has it.
    """

    secret: str | None = None
    pending_secret: str | None = None
    last_step: int | None = None
    enabled_at: datetime | None = None
    grace_until: datetime | None = None

    @property
    def enabled(self) -> bool:
        return self.secret is not None

    def start_grace(self, now: datetime) -> None:
        if self.grace_until is None:
            self.grace_until = now + GRACE

    def grace_over(self, now: datetime) -> bool:
        return self.grace_until is not None and now >= self.grace_until

    def begin_enrolment(self) -> str:
        if self.pending_secret is None:
            self.pending_secret = new_secret()
        return self.pending_secret

    def confirm_enrolment(self, code: str, now: datetime) -> None:
        if self.pending_secret is None:
            raise ValidationError("totp.not_started", fields={"code": "totp.not_started"})
        step = matching_step(self.pending_secret, code, now, last_used=None)
        if step is None:
            raise ValidationError("totp.wrong_code", fields={"code": "totp.wrong_code"})
        self.secret, self.pending_secret = self.pending_secret, None
        self.last_step, self.enabled_at = step, now

    def accept(self, code: str, now: datetime) -> bool:
        """Check a sign-in code and remember its step so it cannot be used again."""
        if self.secret is None:
            return False
        step = matching_step(self.secret, code, now, last_used=self.last_step)
        if step is None:
            return False
        self.last_step = step
        return True

    def reset(self, now: datetime) -> None:
        """Forget the phone (lost or replaced).

        No new grace period: a manager must enrol the new phone at the next
        sign-in, before reaching any other page.
        """
        self.secret = self.pending_secret = self.last_step = self.enabled_at = None
        self.grace_until = now

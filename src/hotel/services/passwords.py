"""Password hashing with scrypt (Python standard library, hashlib.scrypt).

scrypt is deliberately slow and memory-hungry, so an attacker who steals the
database cannot try billions of guesses per second. Each password gets its own
random salt, so identical passwords produce different hashes.

Stored format (all parameters are kept so they can be raised later):

    scrypt$<n>$<r>$<p>$<salt base64>$<key base64>
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

_PREFIX = "scrypt"


@dataclass(frozen=True, slots=True)
class ScryptParams:
    n: int = 2**15  # CPU/memory cost; 2**15 with r=8 uses about 32 MiB and ~50 ms
    r: int = 8
    p: int = 1
    salt_bytes: int = 16
    key_bytes: int = 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class PasswordHasher:
    def __init__(self, params: ScryptParams | None = None) -> None:
        self._params = params or ScryptParams()
        # Used to spend the same time on unknown usernames as on real ones,
        # so response time does not reveal which usernames exist.
        self._dummy_hash = self.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        p = self._params
        salt = secrets.token_bytes(p.salt_bytes)
        key = self._derive(password, salt, p.n, p.r, p.p, p.key_bytes)
        return f"{_PREFIX}${p.n}${p.r}${p.p}${_b64(salt)}${_b64(key)}"

    def verify(self, password: str, encoded: str) -> bool:
        try:
            prefix, n, r, p, salt_b64, key_b64 = encoded.split("$")
            if prefix != _PREFIX:
                return False
            salt = base64.b64decode(salt_b64, validate=True)
            expected = base64.b64decode(key_b64, validate=True)
            actual = self._derive(password, salt, int(n), int(r), int(p), len(expected))
        except ValueError:
            return False
        # Constant-time comparison: does not stop at the first different byte.
        return hmac.compare_digest(actual, expected)

    def verify_dummy(self, password: str) -> None:
        self.verify(password, self._dummy_hash)

    def needs_rehash(self, encoded: str) -> bool:
        p = self._params
        return not encoded.startswith(f"{_PREFIX}${p.n}${p.r}${p.p}$")

    @staticmethod
    def _derive(password: str, salt: bytes, n: int, r: int, p: int, length: int) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=256 * n * r * p + 1024 * 1024,  # OpenSSL's default limit is too low
            dklen=length,
        )

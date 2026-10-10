"""Password rules.

Follows current NIST SP 800-63B guidance: a long minimum length and a
blocklist of known-common passwords, but no forced "one upper case, one
symbol" composition rules, which mostly produce predictable passwords.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hotel.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    min_length: int = 12
    max_length: int = 128
    common_passwords: frozenset[str] = field(default_factory=frozenset, repr=False)

    def check(self, password: str, *, username: str = "") -> None:
        """Raise ValidationError (on the "password" field) if the password is not acceptable."""
        code = self._problem(password, username)
        if code is not None:
            raise ValidationError(
                code,
                fields={"password": code},
                min_length=self.min_length,
                max_length=self.max_length,
            )

    def _problem(self, password: str, username: str) -> str | None:
        if len(password) < self.min_length:
            return "password.too_short"
        if len(password) > self.max_length:
            return "password.too_long"
        lowered = password.casefold()
        if len(set(lowered)) <= 2:
            return "password.too_repetitive"
        if username and username.casefold() in lowered:
            return "password.contains_username"
        if lowered in self.common_passwords:
            return "password.too_common"
        return None

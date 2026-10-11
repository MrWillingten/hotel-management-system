"""Business exceptions.

Every error carries a stable *code* (for example "auth.invalid_credentials")
and named *params*, never a finished English sentence. The web layer turns the
code into a message in the user's language; the CLI uses the English text.
This keeps the domain independent of any interface or language.
"""

from __future__ import annotations

from typing import Any


class HotelError(Exception):
    """Base class for every expected, explainable failure.

    `fields` optionally maps a form field name to an error code, so a form can
    show each message next to the field it concerns.
    """

    code = "error"

    def __init__(
        self,
        code: str | None = None,
        /,
        *,
        fields: dict[str, str] | None = None,
        **params: Any,
    ) -> None:
        self.code = code or type(self).code
        self.params = params
        self.fields = fields or {}
        super().__init__(f"{self.code} {params}" if params else self.code)


class ValidationError(HotelError):
    """Input has the wrong shape or breaks a simple constraint."""

    code = "validation"


class NotFoundError(HotelError):
    code = "not_found"


class BusinessRuleViolation(HotelError):
    code = "business_rule"


class InvalidStateTransitionError(BusinessRuleViolation):
    code = "invalid_state_transition"


class ConflictError(HotelError):
    code = "conflict"


class StaleDataError(ConflictError):
    """Someone else saved the same record first (optimistic locking)."""

    code = "stale_data"


class AuthenticationError(HotelError):
    code = "auth.invalid_credentials"


class PermissionDeniedError(HotelError):
    code = "permission_denied"

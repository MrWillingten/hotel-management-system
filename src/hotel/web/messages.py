"""User-facing text for the error codes raised by the domain and services.

The domain raises codes such as "password.too_short" with parameters such as
min_length=12. This module is the only place where those codes become
sentences, in the user's language.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app
from flask_babel import lazy_gettext as _l

MESSAGES = {
    "error": _l("Something went wrong. Try again."),
    "validation": _l("Some fields need your attention."),
    "not_found": _l("We couldn't find what you were looking for."),
    "conflict": _l("This change conflicts with existing data."),
    "stale_data": _l("Someone else changed this record. Reload the page to see their changes."),
    "business_rule": _l("This operation isn't allowed."),
    "invalid_state_transition": _l("This operation isn't possible in the record's current state."),
    "permission_denied": _l("You don't have permission to do that."),
    "auth.invalid_credentials": _l(
        "Invalid username or password, or the account is temporarily locked."
    ),
    "auth.too_many_attempts": _l(
        "Too many failed sign-in attempts from this computer. Wait a few minutes and try again."
    ),
    "auth.setup_already_done": _l("The first manager account already exists."),
    "username.invalid": _l(
        "Use 3 to 32 characters: letters, digits, dots, hyphens or underscores."
    ),
    "full_name.invalid": _l("Enter a name of 1 to 100 characters."),
    "password.too_short": _l("Use at least %(min_length)s characters."),
    "password.too_long": _l("Use at most %(max_length)s characters."),
    "password.too_repetitive": _l("This password repeats the same characters too much."),
    "password.contains_username": _l("The password must not contain the username."),
    "password.too_common": _l("This password is too common. Choose a less predictable one."),
    "period.departure_not_after_arrival": _l("The departure date must be after the arrival date."),
    "user.username_taken": _l("This username is already used."),
    "user.role_invalid": _l("Choose a role."),
    "user.last_manager": _l("The hotel must keep at least one active manager."),
    "user.cannot_deactivate_self": _l("You can't deactivate your own account."),
    "password.mismatch": _l("The two passwords are different."),
    "password.current_wrong": _l("The current password is not correct."),
    "password.same_as_current": _l("Choose a password different from the current one."),
    "room.number_invalid": _l("Use 1 to 10 letters, digits or hyphens, for example 204 or B-12."),
    "room.number_taken": _l("Another room already has this number."),
    "room.capacity_invalid": _l("Capacity must be between 1 and %(max)s guests."),
    "room.rate_invalid": _l("Enter a nightly rate above 0 and at most 100,000 DT."),
    "room.category_unknown": _l("Choose a category."),
    "category.name_invalid": _l("Enter a name of 1 to 50 characters."),
    "category.name_taken": _l("A category with this name already exists."),
    "description.invalid": _l("Use at most %(max_length)s characters."),
    "notes.invalid": _l("Use at most %(max_length)s characters."),
    "reason.invalid": _l("Enter a reason of at most %(max_length)s characters."),
    "maintenance.reopen_not_after_start": _l(
        "The reopening day must be after the first closed night."
    ),
    "maintenance.in_past": _l("Maintenance can't start in the past."),
    "maintenance.too_long": _l("A maintenance period lasts at most %(max)s nights."),
    "maintenance.conflict": _l(
        "The room is already closed on %(count)s of these nights (%(first)s to %(last)s)."
    ),
    "maintenance.already_over": _l("This maintenance period is already over."),
    "field.not_a_number": _l("Enter a whole number."),
    "field.invalid_date": _l("Enter a valid date."),
    "money.invalid": _l("Enter an amount such as 180 or 180.500."),
    "money.too_many_decimals": _l("Amounts have at most 3 decimals (millimes)."),
}


def message_for(code: str, params: Mapping[str, Any] | None = None) -> str:
    template = MESSAGES.get(code)
    if template is None:
        current_app.logger.warning("No user message for error code %r", code)
        template = MESSAGES["error"]
    try:
        return str(template) % dict(params or {})
    except (KeyError, TypeError, ValueError):
        current_app.logger.warning("Bad parameters %r for error code %r", params, code)
        return str(MESSAGES["error"])

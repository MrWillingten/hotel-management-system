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
    "auth.invalid_code": _l("This code is not correct, or it was already used. Try the next one."),
    "auth.code_expired": _l("The sign-in took too long or failed too often. Start again."),
    "totp.wrong_code": _l("This code is not correct. Check the phone's time and try again."),
    "totp.not_started": _l("Reload the page and scan the new QR code."),
    "totp.not_enabled": _l("Two-factor sign-in is not on."),
    "totp.already_enabled": _l("Two-factor sign-in is already on."),
    "totp.required_for_managers": _l("Managers must keep two-factor sign-in."),
    "reservation.move_unknown_room": _l("This room is not part of the stay any more."),
    "reservation.move_room_already_used": _l(
        "The guests already used that room during this stay. Choose another one."
    ),
    "reservation.move_nothing_left": _l("No night is left to move in this room."),
    "api_token.name_invalid": _l("Enter a name of 1 to 60 characters."),
    "api_token.lifetime_invalid": _l("Choose one of the proposed durations."),
    "api_token.too_many": _l("You already have %(max)s active tokens. Revoke one first."),
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
        "The room is already closed or booked on %(count)s of these nights (%(first)s to %(last)s)."
    ),
    "room.has_future_bookings": _l(
        "This room still has bookings (%(codes)s). Move or cancel them first."
    ),
    "room.capacity_conflict": _l(
        "Some bookings have more guests than this capacity (%(codes)s). Change them first."
    ),
    "maintenance.already_over": _l("This maintenance period is already over."),
    "guest.name_invalid": _l("Use 1 to %(max_length)s letters, spaces, hyphens or apostrophes."),
    "guest.doc_type_invalid": _l("Choose a document type."),
    "guest.cin_invalid": _l("A CIN number has exactly 8 digits."),
    "guest.passport_invalid": _l("A passport number has 5 to 20 letters or digits."),
    "guest.phone_invalid": _l("Enter a phone number of 8 to 15 digits."),
    "guest.email_invalid": _l("Enter a valid e-mail address."),
    "guest.nationality_invalid": _l("Choose a country from the list."),
    "guest.document_taken": _l("A guest with this identity document is already registered."),
    "guest.probable_duplicate": _l(
        "A guest with the same name and phone or e-mail already exists."
    ),
    "guest.reason_required": _l("Give a reason (at most 200 characters)."),
    "reservation.arrival_in_past": _l("The arrival date can't be in the past."),
    "reservation.too_long": _l("A stay lasts at most %(max)s nights."),
    "reservation.too_far": _l("Bookings open at most two years ahead."),
    "reservation.rooms_count": _l("Book between 1 and %(max)s rooms at once."),
    "reservation.room_twice": _l("Each room can only be selected once."),
    "reservation.occupants_invalid": _l("Each room needs at least one adult."),
    "reservation.no_room_selected": _l("Select at least one room."),
    "reservation.guest_do_not_rent": _l(
        "This guest is marked do-not-rent: new reservations are refused."
    ),
    "reservation.room_out_of_service": _l("Room %(room)s is out of service."),
    "reservation.capacity_exceeded": _l(
        "Room %(room)s can sleep at most %(capacity)s guests (%(occupants)s requested)."
    ),
    "reservation.room_unavailable": _l(
        "Room %(room)s is already booked or closed on %(count)s of these nights "
        "(%(first)s to %(last)s)."
    ),
    "reservation.night_taken": _l(
        "Another booking took one of these rooms a moment ago. Search again."
    ),
    "reservation.checked_in_limits": _l(
        "The guest is in the house: only the departure date and the occupants can change."
    ),
    "reservation.departure_in_past": _l("The departure date must be after today."),
    "reservation.not_modifiable": _l("This reservation can no longer be changed."),
    "reservation.not_cancellable": _l("Only a confirmed reservation can be cancelled."),
    "reservation.cancel_after_arrival": _l(
        "The arrival time has passed: record a no-show instead of a cancellation."
    ),
    "reservation.invalid_transition": _l("This isn't possible for a reservation in this state."),
    "reservation.check_in_too_early": _l("Check-in opens on the arrival day (%(arrival)s)."),
    "reservation.check_in_too_late": _l(
        "The stay is already over: this reservation can no longer be checked in."
    ),
    "reservation.room_still_occupied": _l(
        "Room %(room)s is still occupied (%(code)s). Check that guest out first."
    ),
    "reservation.no_show_too_early": _l(
        "A no-show can only be recorded after the check-in time on %(arrival)s."
    ),
    "extra.name_invalid": _l("Enter a name of 1 to 60 characters."),
    "extra.price_invalid": _l("Enter a price above 0 and at most 10,000 DT."),
    "extra.name_taken": _l("A service with this name already exists."),
    "extra.unknown": _l("Choose a service from the catalogue."),
    "charge.not_in_house": _l("Extra services can only be charged while the guest is checked in."),
    "charge.quantity_invalid": _l("The quantity must be between 1 and %(max)s."),
    "charge.date_outside_stay": _l("Choose a date between %(arrival)s and %(last)s."),
    "charge.bill_closed": _l("The bill is closed: this charge can no longer be changed."),
    "charge.already_void": _l("This charge was already voided."),
    "tax.name_invalid": _l("Enter a name of 1 to 60 characters."),
    "tax.kind_invalid": _l("Choose the kind of tax and what it applies to."),
    "tax.rate_invalid": _l("Enter a percentage above 0 and at most 100."),
    "tax.amount_invalid": _l("Enter an amount above 0 and at most 1,000 DT."),
    "tax.per_night_on_services": _l(
        "An amount per adult per night can only apply to the accommodation."
    ),
    "settings.invalid": _l("Some settings are out of range."),
    "settings.out_of_range": _l("This value is out of the allowed range."),
    "field.invalid_percent": _l("Enter a percentage between 0 and 100, for example 20 or 7.5."),
    "field.invalid_time": _l("Enter a time such as 14:00."),
    "discount.rate_invalid": _l("Enter a percentage above 0 and at most 100."),
    "discount.amount_invalid": _l("Enter an amount above 0."),
    "discount.over_cap": _l(
        "Discounts would total %(requested)s DT, above the allowed maximum of %(cap)s DT."
    ),
    "discount.bill_closed": _l("The bill is closed: discounts can no longer change."),
    "payment.amount_invalid": _l("Enter an amount above 0 and at most 1,000,000 DT."),
    "payment.method_invalid": _l("Choose how the money was paid."),
    "payment.more_than_due": _l("That is more than the balance due (%(due)s DT)."),
    "payment.refund_too_large": _l("That is more than the guest overpaid (%(credit)s DT)."),
    "reference.invalid": _l("Use at most %(max_length)s characters."),
    "report.range_reversed": _l("The last night must not be before the first night."),
    "report.range_too_long": _l("A report covers at most %(max)s nights (two years)."),
    "night_audit.day_not_over": _l("Only a day that is over can be closed."),
    "rate_period.name_invalid": _l("Enter a name of 1 to 60 characters."),
    "rate_period.too_long": _l("A rate period lasts at most %(max)s nights."),
    "rate_period.dates_reversed": _l("The last night must not be before the first night."),
    "rate_period.overlap": _l(
        "This category already has a rate on some of these nights (%(name)s)."
    ),
    "guest.anonymised": _l("This guest was anonymised: the record can no longer be used."),
    "guest.not_anonymisable": _l(
        "One of these guests can no longer be anonymised (a new booking?). Reload the list."
    ),
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

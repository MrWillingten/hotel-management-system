"""Content of the walk-through (story 6.14): tour steps and checklist labels.

The tour is a few plain pages (no JavaScript, as everywhere): each step
explains one part of the application and links to it. Receptionists see the
front-desk steps; managers also see the administration steps.
"""

from __future__ import annotations

from dataclasses import dataclass

from flask_babel import lazy_gettext as _l


@dataclass(frozen=True, slots=True)
class TourStep:
    icon: str
    title: object
    text: object
    points: tuple[object, ...]
    endpoint: str | None = None
    manager_only: bool = False


STEPS: tuple[TourStep, ...] = (
    TourStep(
        "home",
        _l("Welcome to the front desk"),
        _l(
            "This short tour shows where everything is. It takes about two minutes; you can skip it and reopen it from Help."
        ),
        (
            _l("The menu on the side opens every page; Help explains each one."),
            _l("EN, FR and ع change the language; the sun and moon change the theme."),
            _l("Your name, top right, opens your account: password and two-factor sign-in."),
        ),
    ),
    TourStep(
        "calendar",
        _l("The dashboard: today at a glance"),
        _l(
            "Every morning starts here: who arrives, who leaves, who is in the house, and which rooms are not ready."
        ),
        (
            _l("Check in and Check out are right next to each guest."),
            _l("Unpaid after departure lists invoices that still owe money."),
            _l("Housekeeping moves rooms from To clean to Ready."),
        ),
        "dashboard.index",
    ),
    TourStep(
        "grid",
        _l("Finding a room and booking it"),
        _l(
            "Availability shows rooms and nights as a grid. New reservation books in three steps: dates, guest, rooms."
        ),
        (
            _l("Search for the guest before registering them, so nobody is registered twice."),
            _l("Each night's price is locked when you book."),
            _l("Review the booking, then confirm it once."),
        ),
        "availability.index",
    ),
    TourStep(
        "bed",
        _l("During the stay"),
        _l("The reservation page holds every action on a stay."),
        (
            _l("Change dates or rooms; Move guests to another room from tonight on."),
            _l("Add extra services such as breakfasts while the guest is checked in."),
            _l("Cancel before arrival (a fee applies within 48 hours) or record a no-show."),
        ),
        "reservations.index",
    ),
    TourStep(
        "archive",
        _l("Money and invoices"),
        _l(
            "The bill shows what the guest owes; check-out issues the invoice, which can never be changed."
        ),
        (
            _l("Record a deposit or a payment with its method and reference."),
            _l("Open an invoice and press Ctrl+P to print it or save it as PDF."),
            _l("Mistakes are corrected with refunds, never by editing."),
        ),
        "invoices.index",
    ),
    TourStep(
        "tools",
        _l("Rooms, prices and staff"),
        _l("As a manager you set up what the hotel sells and who works with you."),
        (
            _l("Rooms: categories, rooms, seasonal rates and maintenance."),
            _l("Settings and taxes: cancellation fee, check-in time, VAT and tourist tax."),
            _l("Staff: create accounts with a temporary password; deactivate, never delete."),
        ),
        "rooms.index",
        manager_only=True,
    ),
    TourStep(
        "shield",
        _l("Figures and safety"),
        _l("The administration pages keep the hotel's numbers and data in good shape."),
        (
            _l("Reports: occupancy, average rate, revenue and balances, with CSV exports."),
            _l("Night audit closes each day; the audit log shows who did what."),
            _l("Backups: copy them regularly to another device."),
        ),
        "reports.index",
        manager_only=True,
    ),
    TourStep(
        "check",
        _l("You are ready"),
        _l(
            "The Getting started list on the dashboard ticks itself as you do each task for the first time."
        ),
        (
            _l("Help, in the menu, explains every page with an example."),
            _l("You can reopen this tour from Help at any time."),
        ),
        "help.index",
    ),
)


def steps_for(is_manager: bool) -> list[TourStep]:
    return [s for s in STEPS if is_manager or not s.manager_only]


# The "Getting started" checklist: label and where to do it, per item key
# (the items and the audit actions that tick them are in domain/onboarding.py).
CHECKLIST_TEXT: dict[str, tuple[object, str]] = {
    "register_guest": (_l("Register a guest"), "guests.create"),
    "book": (_l("Make a reservation"), "reservations.new"),
    "check_in": (_l("Check a guest in"), "dashboard.index"),
    "take_payment": (_l("Record a deposit or a payment"), "reservations.index"),
    "check_out": (_l("Check a guest out"), "dashboard.index"),
    "add_room": (_l("Add a room"), "rooms.create"),
    "add_staff": (_l("Add a staff member"), "staff.create"),
    "two_factor": (_l("Set up two-factor sign-in"), "account.two_factor"),
    "backup": (_l("Make a backup"), "backups.index"),
}

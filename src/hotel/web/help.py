"""Content of the in-app Help page (story 6.10).

A condensed, translated version of docs/user-guide.md: one topic per page
of the application, with what it is for, its main buttons and an example.
Topics marked `manager_only` are shown to managers only, so receptionists
read only about what they can use. The walk-through (story 6.14) links here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from flask_babel import lazy_gettext as _l


@dataclass(frozen=True, slots=True)
class HelpTopic:
    anchor: str  # the #id in the page, also used by the walk-through
    title: object
    purpose: object
    buttons: list[tuple[object, object]] = field(default_factory=list)
    example: object = ""
    manager_only: bool = False
    endpoint: str | None = None  # "Open this page" link


TOPICS: list[HelpTopic] = [
    HelpTopic(
        "signing-in",
        _l("Signing in and your account"),
        _l(
            "Accounts are created by a manager with a temporary password, which you replace at "
            "your first sign-in. Click your name in the top bar to change your password or set up "
            "two-factor sign-in."
        ),
        [
            (
                _l("Two-factor sign-in"),
                _l(
                    "After the password, a six-digit code from an app on your phone. Required for "
                    "managers. Keep the recovery codes safe: each one works once if the phone is lost."
                ),
            ),
            (
                _l("Language and theme"),
                _l(
                    "EN, FR, ع and the sun/moon buttons in the top bar; remembered on this computer."
                ),
            ),
            (
                _l("Sign out"),
                _l(
                    "Ends the session at once. Sessions also end after 30 minutes without activity."
                ),
            ),
        ],
        _l(
            "After 5 wrong passwords the account is locked for 15 minutes; a manager can unlock it."
        ),
        endpoint="account.change_password",
    ),
    HelpTopic(
        "dashboard",
        _l("Dashboard"),
        _l(
            "What needs attention today: arrivals, departures, guests in the house, rooms to clean."
        ),
        [
            (_l("Check in"), _l("Next to an arrival: records that the guest has arrived.")),
            (_l("Check out"), _l("Next to a departure: opens the final bill and the invoice.")),
            (
                _l("Unpaid after departure"),
                _l(
                    "Invoices still owing money after the guest left; open one to record a payment."
                ),
            ),
            (
                _l("Housekeeping"),
                _l("Rooms that are not ready, with a button to move each to its next state."),
            ),
        ],
        _l("Amira arrives at 15:10: find her under Arrivals and press Check in."),
        endpoint="dashboard.index",
    ),
    HelpTopic(
        "availability",
        _l("Availability"),
        _l("A grid of rooms and nights, two weeks at a time: what is free when, at a glance."),
        [
            (_l("Previous week, Today, Next week"), _l("Move through time.")),
            (_l("A free cell"), _l("Starts a booking for that room from that night.")),
        ],
        _l("A couple wants 12–14 July: room 205 is free both nights, so click it on the 12th."),
        endpoint="availability.index",
    ),
    HelpTopic(
        "booking",
        _l("New reservation"),
        _l(
            "Three steps: the stay (dates, guests, category), the guest, then the rooms. Each "
            "night's price is locked when you book; later price changes never alter the booking."
        ),
        [
            (_l("Find rooms"), _l("Lists every room free on every night of the stay.")),
            (
                _l("Choose / Register a new guest"),
                _l("Always search first, so a returning guest is not registered twice."),
            ),
            (
                _l("Review the booking"),
                _l("Shows each night and the total; Confirm booking saves it (only once)."),
            ),
        ],
        _l("Karim, 10–13 July, 2 adults: Find rooms → Book 204 → Review → Confirm booking."),
        endpoint="reservations.new",
    ),
    HelpTopic(
        "reservation",
        _l("A reservation"),
        _l("Everything about one stay, and every action on it."),
        [
            (
                _l("Change"),
                _l(
                    "New dates, rooms or occupants; availability and price are checked again. Nights "
                    "already booked keep their price."
                ),
            ),
            (
                _l("Move"),
                _l(
                    "Moves the guests to another room from tonight on, at the same price by default. "
                    "The old room stays on the bill and goes to the cleaning list."
                ),
            ),
            (
                _l("Cancel reservation"),
                _l(
                    "Free until 48 hours before arrival, then a fee (20 % by default). The exact fee "
                    "is shown before you confirm."
                ),
            ),
            (
                _l("Record a no-show"),
                _l("After the arrival time, for a guest who never came; the rooms are freed."),
            ),
            (
                _l("Extra services"),
                _l(
                    "While the guest is checked in: breakfasts, transfers… with a quantity and date."
                ),
            ),
        ],
        _l("The air conditioning breaks in 204: press Move, choose 205, keep the price."),
        endpoint="reservations.index",
    ),
    HelpTopic(
        "bill",
        _l("Bill and payments"),
        _l("The running bill of a stay, exactly as the invoice will show it."),
        [
            (
                _l("Record a deposit / payment"),
                _l(
                    "Amount, method and an optional reference; never more than the balance due. "
                    "Payments are never edited or deleted."
                ),
            ),
            (
                _l("Grant a discount"),
                _l("Managers: a percentage or fixed amount on accommodation, with a reason."),
            ),
            (_l("Refund the guest"), _l("Managers: when the guest paid more than the total.")),
        ],
        _l("Take a 100 DT deposit by card with the slip number as reference."),
    ),
    HelpTopic(
        "guests",
        _l("Guests"),
        _l(
            "Every guest once, found by name, document, phone or e-mail. Accents and capitals do "
            "not matter."
        ),
        [
            (
                _l("Register a guest"),
                _l("If someone similar exists, the form proposes them first."),
            ),
            (_l("Show"), _l("Reveals a masked document number; the reveal is audited.")),
            (
                _l("Flags"),
                _l("VIP for special attention; Do not rent (managers) refuses new bookings."),
            ),
        ],
        _l("Search “dupont” before registering Lucas Dupont: he may already be there."),
        endpoint="guests.index",
    ),
    HelpTopic(
        "invoices",
        _l("Invoices"),
        _l(
            "Issued at check-out (and for cancellation or no-show fees), numbered without gaps, and "
            "never changed afterwards: corrections are payments or refunds."
        ),
        [(_l("Print or save as PDF"), _l("Open an invoice and press Ctrl+P."))],
        _l("Re-print last week's invoice for a company: search its number or the guest's name."),
        endpoint="invoices.index",
    ),
    HelpTopic(
        "rooms",
        _l("Rooms and housekeeping"),
        _l(
            "Every room with its status tonight. Housekeeping: To clean → Cleaned, to inspect → "
            "Ready. Only a ready room should be given to a guest."
        ),
        [
            (_l("Mark cleaned"), _l("The cleaner has finished.")),
            (_l("Mark inspected"), _l("A second person checked it: the room is ready.")),
            (_l("Mark to clean"), _l("Sends a room back.")),
        ],
        _l("After a check-out, 204 is To clean; the cleaner marks it cleaned, you inspect it."),
        endpoint="rooms.index",
    ),
    HelpTopic(
        "room-admin",
        _l("Rooms, prices and maintenance"),
        _l("Managers set up the rooms the hotel sells and their prices."),
        [
            (_l("Categories"), _l("Group rooms (Standard, Deluxe…); needed before adding rooms.")),
            (_l("Add a room / Edit room"), _l("Number, category, capacity, nightly price.")),
            (
                _l("Close for maintenance"),
                _l("Blocks a room between two dates; refused over existing bookings."),
            ),
            (
                _l("Seasonal rates"),
                _l("A different price for a category between two dates (e.g. summer)."),
            ),
        ],
        _l("Paint 204 from 3 to 6 July: room page → Close for maintenance."),
        manager_only=True,
        endpoint="rooms.index",
    ),
    HelpTopic(
        "reports",
        _l("Reports"),
        _l(
            "Occupancy, average daily rate, revenue per available room, money invoiced and "
            "received, cancellations, outstanding balances, for any range up to two years."
        ),
        [(_l("CSV"), _l("Downloads a table for Excel or LibreOffice; exports are audited."))],
        _l("Compare July 2026 with July 2025 before setting summer prices."),
        manager_only=True,
        endpoint="reports.index",
    ),
    HelpTopic(
        "night-audit",
        _l("Night audit"),
        _l(
            "Closes a finished day: guests who never came become no-shows and the day's figures "
            "are frozen. Missed days are closed automatically at start-up."
        ),
        [(_l("Close the day"), _l("Yesterday by default; running it twice changes nothing."))],
        _l("Every morning, check that yesterday is in the list of closed days."),
        manager_only=True,
        endpoint="night_audit.index",
    ),
    HelpTopic(
        "settings",
        _l("Extra services, settings and taxes"),
        _l("The catalogue of chargeable services, the hotel's rules and its taxes."),
        [
            (
                _l("Extra services"),
                _l("Name and price; a new price applies to future charges only."),
            ),
            (
                _l("Settings"),
                _l(
                    "Check-in and check-out times, cancellation fee and window, discount cap, "
                    "weekend surcharge, anonymisation delay."
                ),
            ),
            (
                _l("Tax rules"),
                _l("A percentage (VAT) or an amount per adult per night (tourist tax)."),
            ),
        ],
        _l("Breakfast goes from 15 to 18 DT: edit it; breakfasts already charged keep 15 DT."),
        manager_only=True,
        endpoint="extras.index",
    ),
    HelpTopic(
        "staff",
        _l("Staff"),
        _l("Managers create accounts; accounts are deactivated, never deleted."),
        [
            (_l("Add a staff member"), _l("With a temporary password replaced at first sign-in.")),
            (_l("Set temporary password / Unlock"), _l("For a forgotten password or a lock.")),
            (_l("Deactivate account"), _l("Signs the person out everywhere, at once.")),
        ],
        _l("An employee leaves: open their account and deactivate it."),
        manager_only=True,
        endpoint="staff.index",
    ),
    HelpTopic(
        "safety",
        _l("Audit log, backups and privacy"),
        _l("The tools that keep the hotel's data trustworthy and safe."),
        [
            (
                _l("Audit log"),
                _l("Who did what and when; altered or removed entries are detected and shown."),
            ),
            (
                _l("Back up now"),
                _l(
                    "A verified copy of the database; one is also made every day. Copy the backups "
                    "to another device regularly."
                ),
            ),
            (
                _l("Anonymise old guests"),
                _l("Erases the personal data of guests without a stay for a long time."),
            ),
            (
                _l("API tokens"),
                _l("Let another program read (never change) the hotel's figures; in your account."),
            ),
        ],
        _l("“Who refunded 46 DT on R-2026-00031?”: filter the audit log by action."),
        manager_only=True,
        endpoint="audit.index",
    ),
]


def topics_for(is_manager: bool) -> list[HelpTopic]:
    return [t for t in TOPICS if is_manager or not t.manager_only]

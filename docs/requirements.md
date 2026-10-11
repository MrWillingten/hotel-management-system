# Requirements analysis

Source: *Python Semester Project – Project 3: Hotel Reservation and Management System*.
This document restates the client's needs, records every decision taken where the
brief was ambiguous, and is the reference for the tests.

## 1. Summary

A single hotel in Tunisia manages reservations with spreadsheets, phone calls and
paper, which causes double bookings, wrong bills and no view of occupancy or
revenue. The system replaces this with one staff-facing application: it keeps
rooms and guests, books rooms for date ranges without conflicts, handles changes
and cancellations (with a fee), records arrivals and departures, adds extra
services to a stay, produces an itemised bill with taxes, payments and balance,
and gives management occupancy and revenue reports. Data survives restarts and
every invalid operation is refused with a clear explanation.

## 2. Actors

| Actor | Uses the system | Responsibilities |
|---|---|---|
| Receptionist | Yes | Guests; reservations (create, modify, cancel); check-in and check-out; service charges; payments; printing bills |
| Manager | Yes | Everything a receptionist does, plus rooms, prices, services, maintenance, discounts, taxes, settings, statistics and staff accounts |
| Guest | No (external) | Subject of the data; contacts the hotel by phone or in person |
| System clock | Implicit | Defines "today", the 48-hour cancellation window and arrivals/departures |

Guests do not sign in. A public booking site would multiply the attack surface for little value.

## 3. Entities

Room category, room, maintenance period, guest, reservation, reserved room (link),
room night, service, service charge, payment, discount, tax rule, invoice, invoice
line, staff user, user session, audit log entry, setting. See
[data-model.md](data-model.md).

## 4. Business rules

### From the brief (BR1–BR12)

1. Each room has a unique room number.
2. Guests are identifiable by their registration information.
3. A room cannot have overlapping confirmed reservations.
4. The departure date is later than the arrival date (at least one night).
5. A room under maintenance cannot be reserved for the affected period.
6. A reservation cannot be confirmed without an available room.
7. The number of occupants cannot exceed the room's capacity.
8. Accommodation cost = nights × applicable nightly rates.
9. Additional services are included in the final bill.
10. A guest may pay a deposit before arrival.
11. A 20 % cancellation fee applies when a confirmed reservation is cancelled less than 48 hours before arrival.
12. Invalid operations are rejected and clearly explained.

### Derived (design decisions)

13. Stays are half-open intervals `[arrival, departure)`. Two stays overlap if and only if `a1 < d2 and a2 < d1`; a guest may arrive on the day another leaves.
14. Nights = departure − arrival in days.
15. Every active status (CONFIRMED, CHECKED_IN) blocks the room, not only CONFIRMED.
16. Lifecycle: `CONFIRMED → CHECKED_IN → CHECKED_OUT`, `CONFIRMED → CANCELLED`, `CONFIRMED → NO_SHOW`. Anything else is refused.
17. Check-in only for a CONFIRMED reservation on a valid date, and never while the previous guest of that room is still checked in.
18. Modifications re-run every availability check, excluding the reservation itself. What may change depends on the status.
19. Service charges only while CHECKED_IN, dated within the stay.
20. Prices are locked in at booking, **per night**; later price changes never alter existing reservations or invoices.
21. Payments and prices are positive; balance = total − paid; a negative balance means a refund is owed.
22. An issued invoice is immutable; corrections are new entries.
23. The room status for a date is derived: unavailable (maintenance/out of service) > occupied > reserved > available.
24. Money is in Tunisian dinars with 3 decimals (millimes), stored as integer millimes, never as floats.
25. A receptionist searches for an existing guest before registering a new one; probable duplicates are flagged.
26. Records with history (guests, rooms, services, users) are deactivated, never deleted.

## 5. Decisions on ambiguous points

| # | Question | Decision |
|---|---|---|
| Q1 | "One or more rooms" per reservation | One reservation may hold several rooms, all with the same dates; adults and children recorded per room. |
| Q2 | Cancellation fee details | 20 % of accommodation after discount, before tax. "Less than 48 h": exactly 48:00 → no fee. Reference time = arrival date + configurable check-in time (14:00). Fee taken from the deposit first; any remainder refunded, any shortfall owed. Shortening a stay never charges a fee (documented limitation). Cancelling after arrival is not possible: use no-show. Grace period setting, default 0. The fee is not taxed. |
| Q3 | Discounts | Manager only; percentage or fixed amount; reason required; total discount capped (default 30 %); accommodation only; audited. |
| Q4 | Guest identity | Identity document type (CIN / passport) + number is unique; phone and e-mail are contact fields. |
| Q5 | Deployment | Several staff may use it at once (concurrency handled); runs on 127.0.0.1 by default; LAN use requires HTTPS through a reverse proxy. |
| A | Pricing | One hotel, one currency (TND); nightly price per room; seasonal rates added later as an extra. |
| B | Confirmation | Reservations are created CONFIRMED; the deposit is optional. |
| C | Service charges | Only while CHECKED_IN. |
| D | Staff accounts | Created by managers; no self-registration. |
| E | Maintenance vs. bookings | Scheduling maintenance over a confirmed reservation is refused with the list of affected reservations. |
| F | Early departure / no-show | Early departure: only the nights actually stayed are charged (at least one); the others are released. No-show: recorded after the arrival time, charged like a late cancellation. |
| G | **Taxes** | **In scope.** Configurable tax rules (percentage, e.g. VAT; per adult per night, e.g. tourist tax). Prices are stored tax-exclusive; each tax is its own invoice line, copied onto the invoice when issued. Real rates must be verified with current Tunisian regulations. |
| H | Occupancy rate | Room-nights sold ÷ room-nights available, excluding rooms under maintenance. |

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Platform | Python ≥ 3.11; Windows 10/11 and mainstream Linux distributions; works offline (all fonts and assets bundled) |
| Interface | Web interface on localhost; responsive from 360 px phones to wide screens; light, dark and system themes; English, French and Arabic (right-to-left) |
| Persistence | Embedded SQLite, no database server; atomic transactions; backups and integrity checks |
| Security | Staff authentication with roles; deny-by-default access control; CSRF protection; secure headers; audit log. See [security.md](security.md). |
| Accessibility | WCAG AA contrast, keyboard navigation, visible focus, reduced-motion support, 200 % zoom |
| Quality | OOP, layered architecture, automated tests (unit, integration, end-to-end), CI on Linux and Windows, coverage ≥ 90 % |

## 7. Main scenarios (from the brief, each becomes a named acceptance test)

| Brief | Scenario | Expected result |
|---|---|---|
| §4.1 | Room 204 (deluxe, 180 DT) closed for maintenance for three days | No reservation can cover that period |
| §4.2 | A returning guest calls | The existing record is found, not duplicated |
| §4.3 | Request 10–15 July, room booked 12–14 July | Conflict refused; alternative rooms suggested |
| §4.4 | Extend a stay from 3 to 5 nights | Allowed only if the room is free for the extra nights |
| §4.5 | Guest with a confirmed reservation arrives, later leaves | Check-in recorded; final statement includes services |
| §4.6 | 4 nights, 3 breakfasts, 1 airport transfer | All charges on the final bill |
| §4.7 | 3 nights × 150 DT, 80 DT services, 100 DT deposit | Total and remaining balance computed exactly |
| §4.8 | Management statistics | Reservations, occupancy, categories, revenues, cancellations, balances, availability |

# ADR 0004 – One row per room per night (`room_night`)

**Status:** accepted. Sprint 2 created the table for maintenance nights;
Sprint 3 adds reservation nights.

## Context
Preventing double bookings only in Python means one forgotten check, or two
receptionists booking at the same moment, can still create an overlap. SQLite
cannot express "no overlapping date ranges" as a constraint.

## Decision
Every booked or blocked night is a row `(room_id, night, reservation_id |
maintenance_id, rate_mill)` with `UNIQUE(room_id, night)`. Reservations and
maintenance both write rows; cancelling deletes them. Availability is checked
in Python inside a `BEGIN IMMEDIATE` transaction, and the unique constraint is
the final guard.

## Consequences
The database itself makes double booking impossible. Prices are stored per
night, which makes stay extensions and seasonal rates straightforward, and
occupancy reports become simple counts. Cost: one row per night (stays are
capped at 60 nights).

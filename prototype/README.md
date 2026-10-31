# Checkpoint 2: procedural prototype

The core rules of the Hotel Reservation and Management System, written with
**functions and Python's built-in collections only** (`dict`, `list`,
`tuple`, `set`): no classes, no database, no web interface. It follows the
CP1 analysis: the same entities, business rules and scenarios.

```
python prototype/hotel_prototype.py     # terminal menu, with sample rooms and services
python prototype/scenarios.py           # the brief's scenarios, each checked
```

No installation is needed (Python 3.11 or later, standard library only).

## How the data is kept

One dictionary, `hotel`, holds one collection per table of the CP1 ER diagram:

| Key | Collection | Why this collection |
|---|---|---|
| `categories`, `guests`, `reservations`, `extras`, `maintenance` | `dict` id → row (a `dict`) | find a row by its id at once |
| `rooms` | `dict` room number → row | the number is unique (BR1), so it is the key |
| `room_nights` | `dict` **(room, night)** → who holds it and its locked rate | the key is a `tuple`, like the primary key (room_id, night) of the ER diagram: a night cannot be taken twice (BR3, BR5) |
| `charges`, `payments` | `list` of rows | kept in the order they happened |
| `TRANSITIONS` | `dict` status → `set` of next statuses | the reservation life cycle (BR16) |
| `MENU` | `dict` choice → (label, function) | the whole menu as data |

Money is an `int` number of millimes (1 DT = 1000 millimes), and amounts
typed by the user are read as text (`dinars("12.500")`), never as `float`
(BR24).

## Where each CP1 rule is

| CP1 | Function(s) in `hotel_prototype.py` |
|---|---|
| BR1 unique room numbers | `add_room` |
| BR2, BR25 guests identified, search before registering | `register_guest`, `find_guests` |
| BR3, BR5, BR6, BR15 no double booking, maintenance, available room | `is_free`, `available_rooms`, `book`, `close_for_maintenance` |
| BR4, BR13, BR14 dates, half-open stays, nights | `check_period`, `overlaps`, `each_night`, `nights` |
| BR7 capacity | `book` |
| BR8, BR9, BR21 bill, services, balance | `accommodation`, `bill` |
| BR10 deposit | `record_payment` |
| BR11 + decision Q2 cancellation fee (20 %, under 48 h before 14:00) | `late_fee`, `cancel` |
| BR12 invalid operations refused and explained | every function raises `ValueError` with the reason; the menu prints it |
| BR16 life cycle | `TRANSITIONS`, `set_status` |
| BR17 check-in | `check_in` |
| BR18 modification re-checks availability | `change_dates` (`is_free(..., ignore=...)`) |
| BR19 services only while checked in | `charge_extra` |
| BR20 price locked per night | `book` stores the rate in `room_nights`; `change_dates` keeps it |
| BR23 room status for a day | `room_status` |
| BR24 money in millimes | `dinars`, `fmt` |
| Decision F no-show | `no_show` |

The scenarios of CP1 section 2.6 are the functions in `scenarios.py`, with
the same rooms, dates and amounts (for example 3 nights × 150 DT + 80 DT of
services − 100 DT deposit → total 530 DT, balance 430 DT).

## Not in the prototype (later checkpoints)

Staff accounts and roles, taxes, discounts, reports, saving the data and the
web interface. They come with the object-oriented design (CP3) and the
integration (CP4).

## Relation to the application

The full application in `src/hotel/` was built first, with classes, a
database and a web interface. This prototype writes its core rules again in
the procedural style that CP2 asks for. The same ideas reappear as classes,
for example `nights()` → `StayPeriod.nights`, `room_nights` → the
`room_night` table, `TRANSITIONS` → `Reservation` status changes,
`bill()` → `build_bill()`.

The test suite runs every scenario (`tests/unit/test_prototype.py`).

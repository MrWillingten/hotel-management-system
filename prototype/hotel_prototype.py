"""Checkpoint 2 - procedural prototype of the Hotel Reservation and Management System.

The core rules of the CP1 analysis written with functions and the built-in
collections only (dict, list, tuple, set): no classes, no database, no web.
Comments name the business rule (BR) or decision of CP1 each function enforces.

    python prototype/hotel_prototype.py      # terminal menu
    python prototype/scenarios.py            # the brief's scenarios, checked

All the data lives in one dictionary, `hotel`, whose keys mirror the tables of
the CP1 ER diagram. Money is an integer number of millimes (1 DT = 1000
millimes) so no rounding error is possible (BR24).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

HOTEL_TIME_ZONE = ZoneInfo("Africa/Tunis")
CHECK_IN_TIME = time(14, 0)  # decision Q2: reference time for the 48-hour rule
CANCELLATION_WINDOW = timedelta(hours=48)  # BR11
CANCELLATION_FEE_PERCENT = 20  # BR11

# BR16: the only allowed changes of status.
TRANSITIONS = {
    "CONFIRMED": {"CHECKED_IN", "CANCELLED", "NO_SHOW"},
    "CHECKED_IN": {"CHECKED_OUT"},
}
ACTIVE = {"CONFIRMED", "CHECKED_IN"}  # BR15: statuses that hold a room


# ---------------------------------------------------------------- data
def new_hotel() -> dict:
    """An empty hotel: one collection per table of the ER diagram."""
    # Each key is a table of the ER diagram. Rows are dicts with the same fields;
    # a dict keyed by id (or room number, unique by BR1) finds a row at once.
    return {
        "categories": {},  # id -> category
        "rooms": {},  # room number -> room
        "maintenance": {},  # id -> maintenance period
        "guests": {},  # id -> guest
        "reservations": {},  # id -> reservation (with its list of rooms)
        "room_nights": {},  # (room, night) -> who holds that night, and its locked rate
        "extras": {},  # id -> extra service
        "charges": [],  # service charges, in the order they were made
        "payments": [],  # deposits and payments, in the order they were received
        "next_id": {"category": 1, "maintenance": 1, "guest": 1, "reservation": 1, "extra": 1},
    }


def next_id(hotel: dict, table: str) -> int:
    number = hotel["next_id"][table]
    hotel["next_id"][table] = number + 1
    return number


# ---------------------------------------------------------------- money (BR24)
def dinars(text: str) -> int:
    """'150' or '12.500' -> millimes. Parsed as text, never as a float."""
    text = text.strip()
    whole, _, fraction = text.partition(".")
    if not whole.isdigit() or (fraction and not fraction.isdigit()) or len(fraction) > 3:
        raise ValueError(f"'{text}' is not an amount in dinars (e.g. 150 or 12.500).")
    return int(whole) * 1000 + int(fraction.ljust(3, "0"))


def fmt(millimes: int) -> str:
    sign = "-" if millimes < 0 else ""
    whole, rest = divmod(abs(millimes), 1000)
    return f"{sign}{whole}.{rest:03d} DT"


# ---------------------------------------------------------------- periods (BR4, BR13, BR14)
def check_period(arrival: date, departure: date) -> None:
    if departure <= arrival:  # BR4
        raise ValueError("The departure date must be after the arrival date (at least one night).")


def nights(arrival: date, departure: date) -> int:
    return (departure - arrival).days  # BR14


def each_night(arrival: date, departure: date) -> list[date]:
    """The nights of a stay: [arrival, departure) - the departure day is not a night (BR13)."""
    return [arrival + timedelta(days=i) for i in range(nights(arrival, departure))]


def overlaps(arrival1: date, departure1: date, arrival2: date, departure2: date) -> bool:
    """BR13: half-open intervals overlap iff a1 < d2 and a2 < d1."""
    return arrival1 < departure2 and arrival2 < departure1


# ---------------------------------------------------------------- rooms
def add_category(hotel: dict, name: str, description: str = "") -> int:
    if any(c["name"].lower() == name.lower() for c in hotel["categories"].values()):
        raise ValueError(f"The category '{name}' already exists.")
    category_id = next_id(hotel, "category")
    hotel["categories"][category_id] = {"id": category_id, "name": name, "description": description}
    return category_id


def add_room(hotel: dict, number: str, category_id: int, capacity: int, nightly_rate: int) -> None:
    if number in hotel["rooms"]:  # BR1
        raise ValueError(f"Room {number} already exists: room numbers are unique.")
    if category_id not in hotel["categories"]:
        raise ValueError("Unknown room category.")
    if capacity < 1 or nightly_rate <= 0:
        raise ValueError("Capacity and nightly rate must be positive.")
    hotel["rooms"][number] = {
        "number": number,
        "category_id": category_id,
        "capacity": capacity,
        "nightly_rate": nightly_rate,
        "in_service": True,
    }


def close_for_maintenance(hotel: dict, room: str, start: date, end: date, reason: str) -> int:
    """BR5 and decision E: refused over existing bookings, listing them."""
    get_room(hotel, room)
    check_period(start, end)
    clashes = set()
    for night in each_night(start, end):
        entry = hotel["room_nights"].get((room, night))
        if entry and "reservation_id" in entry:
            clashes.add(hotel["reservations"][entry["reservation_id"]]["code"])
        elif entry:
            clashes.add("another maintenance period")
    if clashes:
        raise ValueError(f"Room {room} is already taken then: {', '.join(sorted(clashes))}.")
    maintenance_id = next_id(hotel, "maintenance")
    hotel["maintenance"][maintenance_id] = {
        "id": maintenance_id,
        "room": room,
        "start": start,
        "end": end,
        "reason": reason,
    }
    for night in each_night(start, end):
        hotel["room_nights"][(room, night)] = {"maintenance_id": maintenance_id}
    return maintenance_id


def get_room(hotel: dict, number: str) -> dict:
    if number not in hotel["rooms"]:
        raise ValueError(f"There is no room {number}.")
    return hotel["rooms"][number]


def room_status(hotel: dict, room: str, day: date) -> str:
    """BR23: unavailable > occupied > reserved > available."""
    entry = hotel["room_nights"].get((room, day))
    if not hotel["rooms"][room]["in_service"] or (entry and "maintenance_id" in entry):
        return "unavailable"
    if entry:
        status = hotel["reservations"][entry["reservation_id"]]["status"]
        return "occupied" if status == "CHECKED_IN" else "reserved"
    return "available"


# ---------------------------------------------------------------- guests (BR2, BR25)
def register_guest(
    hotel: dict,
    first_name: str,
    last_name: str,
    id_doc_type: str,
    id_doc_number: str,
    phone: str = "",
    email: str = "",
) -> int:
    id_doc_type = id_doc_type.upper()
    if id_doc_type not in ("CIN", "PASSPORT"):
        raise ValueError("The identity document is a CIN or a PASSPORT.")
    if id_doc_type == "CIN" and not (id_doc_number.isdigit() and len(id_doc_number) == 8):
        raise ValueError("A CIN number has exactly 8 digits.")
    if not first_name.strip() or not last_name.strip():
        raise ValueError("First and last names are required.")
    for guest in hotel["guests"].values():  # BR2: document type + number is unique
        if (guest["id_doc_type"], guest["id_doc_number"]) == (id_doc_type, id_doc_number.upper()):
            raise ValueError(
                f"This document already belongs to {guest['first_name']} {guest['last_name']}."
            )
    guest_id = next_id(hotel, "guest")
    hotel["guests"][guest_id] = {
        "id": guest_id,
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "id_doc_type": id_doc_type,
        "id_doc_number": id_doc_number.upper(),
        "phone": phone.strip(),
        "email": email.strip().lower(),
    }
    return guest_id


def find_guests(hotel: dict, text: str) -> list[dict]:
    """BR25: search before registering - by name, document, phone or e-mail."""
    text = text.strip().lower()
    fields = ("first_name", "last_name", "id_doc_number", "phone", "email")
    return [g for g in hotel["guests"].values() if any(text in str(g[f]).lower() for f in fields)]


# ---------------------------------------------------------------- availability (BR3, BR5, BR6)
def is_free(
    hotel: dict, room: str, arrival: date, departure: date, ignore: int | None = None
) -> bool:
    """A room is free if none of its nights is taken - except by reservation `ignore` (BR18)."""
    if not get_room(hotel, room)["in_service"]:
        return False
    for night in each_night(arrival, departure):
        entry = hotel["room_nights"].get((room, night))
        if entry is None:
            continue
        # A maintenance night has no reservation_id: it is never "this reservation".
        if ignore is None or entry.get("reservation_id") != ignore:
            return False
    return True


def available_rooms(hotel: dict, arrival: date, departure: date, people: int = 1) -> list[str]:
    check_period(arrival, departure)
    return sorted(
        number
        for number, room in hotel["rooms"].items()
        if room["capacity"] >= people and is_free(hotel, number, arrival, departure)
    )


# ---------------------------------------------------------------- reservations
def book(
    hotel: dict,
    guest_id: int,
    arrival: date,
    departure: date,
    rooms: list[tuple[str, int, int]],
) -> int:
    """rooms = [(room number, adults, children), ...] - one or more rooms, same dates (Q1)."""
    check_period(arrival, departure)
    if guest_id not in hotel["guests"]:
        raise ValueError("Unknown guest: register or find the guest first.")
    if not rooms:
        raise ValueError("Choose at least one room.")
    if len({number for number, _, _ in rooms}) != len(rooms):
        raise ValueError("The same room is listed twice.")
    for number, adults, children in rooms:
        room = get_room(hotel, number)
        if adults < 1 or children < 0:
            raise ValueError("Each room needs at least one adult.")
        if adults + children > room["capacity"]:  # BR7
            raise ValueError(f"Room {number} sleeps {room['capacity']}, not {adults + children}.")
        if not is_free(hotel, number, arrival, departure):  # BR3, BR5, BR6
            alternatives = available_rooms(hotel, arrival, departure, adults + children)
            free = ", ".join(alternatives) or "none"
            raise ValueError(f"Room {number} is not free for these dates. Free rooms: {free}.")
    reservation_id = next_id(hotel, "reservation")
    hotel["reservations"][reservation_id] = {
        "id": reservation_id,
        "code": f"R-{arrival.year}-{reservation_id:05d}",
        "guest_id": guest_id,
        "arrival": arrival,
        "departure": departure,
        "status": "CONFIRMED",  # decision B: created confirmed, deposit optional
        "rooms": [{"room": n, "adults": a, "children": c} for n, a, c in rooms],
        "cancellation_fee": 0,
    }
    for number, _, _ in rooms:
        for night in each_night(arrival, departure):
            # BR20: the price is locked now, night by night.
            hotel["room_nights"][(number, night)] = {
                "reservation_id": reservation_id,
                "rate": hotel["rooms"][number]["nightly_rate"],
            }
    return reservation_id


def get_reservation(hotel: dict, reservation_id: int) -> dict:
    if reservation_id not in hotel["reservations"]:
        raise ValueError(f"There is no reservation {reservation_id}.")
    return hotel["reservations"][reservation_id]


def set_status(reservation: dict, new_status: str) -> None:
    """BR16: refuse any change of status that is not in TRANSITIONS."""
    if new_status not in TRANSITIONS.get(reservation["status"], set()):
        raise ValueError(f"A {reservation['status']} reservation cannot become {new_status}.")
    reservation["status"] = new_status


def booked_nights(hotel: dict, reservation_id: int) -> dict:
    """{(room, night): rate} of one reservation."""
    return {
        key: entry["rate"]
        for key, entry in hotel["room_nights"].items()
        if entry.get("reservation_id") == reservation_id
    }


def release_nights(hotel: dict, reservation_id: int) -> None:
    for key in list(booked_nights(hotel, reservation_id)):
        del hotel["room_nights"][key]


def change_dates(hotel: dict, reservation_id: int, arrival: date, departure: date) -> None:
    """BR18: check again, ignoring this reservation. BR20: kept nights keep their price."""
    reservation = get_reservation(hotel, reservation_id)
    if reservation["status"] != "CONFIRMED":
        raise ValueError("Only a confirmed reservation that has not started can change its dates.")
    check_period(arrival, departure)
    for line in reservation["rooms"]:
        if not is_free(hotel, line["room"], arrival, departure, ignore=reservation_id):
            raise ValueError(f"Room {line['room']} is not free for the new dates.")
    old_rates = booked_nights(hotel, reservation_id)
    release_nights(hotel, reservation_id)
    for line in reservation["rooms"]:
        room = line["room"]
        for night in each_night(arrival, departure):
            rate = old_rates.get((room, night), hotel["rooms"][room]["nightly_rate"])
            hotel["room_nights"][(room, night)] = {"reservation_id": reservation_id, "rate": rate}
    reservation["arrival"], reservation["departure"] = arrival, departure


def accommodation(hotel: dict, reservation_id: int) -> int:
    """BR8: the sum of the locked nightly rates."""
    return sum(booked_nights(hotel, reservation_id).values())


def late_fee(hotel: dict, reservation: dict, now: datetime) -> int:
    """BR11 + Q2: 20 % of the accommodation if less than 48 hours before arrival at 14:00."""
    arrival_time = datetime.combine(reservation["arrival"], CHECK_IN_TIME)
    if arrival_time - now >= CANCELLATION_WINDOW:  # exactly 48:00 -> no fee
        return 0
    return accommodation(hotel, reservation["id"]) * CANCELLATION_FEE_PERCENT // 100


def cancel(hotel: dict, reservation_id: int, now: datetime) -> int:
    reservation = get_reservation(hotel, reservation_id)
    if reservation["status"] == "CONFIRMED" and now >= datetime.combine(
        reservation["arrival"], CHECK_IN_TIME
    ):
        raise ValueError("The arrival time has passed: record a no-show instead (decision F).")
    fee = late_fee(hotel, reservation, now) if reservation["status"] == "CONFIRMED" else 0
    set_status(reservation, "CANCELLED")
    reservation["cancellation_fee"] = fee
    release_nights(hotel, reservation_id)
    return fee


def no_show(hotel: dict, reservation_id: int, now: datetime) -> int:
    """Decision F: after the arrival time, charged like a late cancellation."""
    reservation = get_reservation(hotel, reservation_id)
    if now < datetime.combine(reservation["arrival"], CHECK_IN_TIME):
        raise ValueError("A no-show can only be recorded after the arrival time.")
    fee = accommodation(hotel, reservation_id) * CANCELLATION_FEE_PERCENT // 100
    set_status(reservation, "NO_SHOW")
    reservation["cancellation_fee"] = fee
    release_nights(hotel, reservation_id)
    return fee


def check_in(hotel: dict, reservation_id: int, today: date) -> None:
    """BR17: confirmed, on a valid date, and the previous guest has left."""
    reservation = get_reservation(hotel, reservation_id)
    if not reservation["arrival"] <= today < reservation["departure"]:
        raise ValueError(f"Check-in is possible from {reservation['arrival']} only.")
    for line in reservation["rooms"]:
        for other in hotel["reservations"].values():
            if (
                other["id"] != reservation_id
                and other["status"] == "CHECKED_IN"
                and any(r["room"] == line["room"] for r in other["rooms"])
            ):
                raise ValueError(
                    f"Room {line['room']}: the previous guest has not checked out yet."
                )
    set_status(reservation, "CHECKED_IN")


def check_out(hotel: dict, reservation_id: int) -> dict:
    reservation = get_reservation(hotel, reservation_id)
    set_status(reservation, "CHECKED_OUT")
    return bill(hotel, reservation_id)


# ---------------------------------------------------------------- services and payments
def add_extra(hotel: dict, name: str, unit_price: int) -> int:
    if unit_price <= 0:  # BR21
        raise ValueError("A price is positive.")
    extra_id = next_id(hotel, "extra")
    hotel["extras"][extra_id] = {"id": extra_id, "name": name, "unit_price": unit_price}
    return extra_id


def charge_extra(hotel: dict, reservation_id: int, extra_id: int, quantity: int, day: date) -> None:
    """BR19: only while checked in, dated within the stay. The price is copied (BR20)."""
    reservation = get_reservation(hotel, reservation_id)
    if reservation["status"] != "CHECKED_IN":
        raise ValueError("Extra services are charged only while the guest is checked in.")
    if not reservation["arrival"] <= day <= reservation["departure"]:
        raise ValueError("The date must be within the stay.")
    if extra_id not in hotel["extras"] or quantity < 1:
        raise ValueError("Choose a known service and a quantity of at least 1.")
    extra = hotel["extras"][extra_id]
    hotel["charges"].append(
        {
            "reservation_id": reservation_id,
            "extra_id": extra_id,
            "description": extra["name"],
            "quantity": quantity,
            "unit_price": extra["unit_price"],
            "date": day,
        }
    )


def record_payment(hotel: dict, reservation_id: int, amount: int, method: str = "CASH") -> None:
    """BR10: a deposit before arrival, a payment afterwards; BR21: always positive."""
    reservation = get_reservation(hotel, reservation_id)
    if amount <= 0:
        raise ValueError("A payment is a positive amount.")
    if method not in ("CASH", "CARD", "TRANSFER"):
        raise ValueError("The method is CASH, CARD or TRANSFER.")
    kind = "DEPOSIT" if reservation["status"] == "CONFIRMED" else "PAYMENT"
    hotel["payments"].append(
        {"reservation_id": reservation_id, "amount": amount, "kind": kind, "method": method}
    )


# ---------------------------------------------------------------- the bill (BR8, BR9, BR21)
def bill(hotel: dict, reservation_id: int) -> dict:
    """Lines, total, paid and balance (balance < 0: a refund is owed)."""
    reservation = get_reservation(hotel, reservation_id)
    lines = []
    if reservation["status"] in ("CANCELLED", "NO_SHOW"):
        if reservation["cancellation_fee"]:
            lines.append(("Cancellation fee", 1, reservation["cancellation_fee"]))
    else:
        per_room_rate: dict[tuple[str, int], int] = {}  # (room, rate) -> number of nights
        for (room, _night), rate in booked_nights(hotel, reservation_id).items():
            per_room_rate[(room, rate)] = per_room_rate.get((room, rate), 0) + 1
        for (room, rate), count in sorted(per_room_rate.items()):
            lines.append((f"Room {room} - nights at {fmt(rate)}", count, count * rate))
    for charge in hotel["charges"]:  # BR9
        if charge["reservation_id"] == reservation_id:
            amount = charge["quantity"] * charge["unit_price"]
            lines.append((charge["description"], charge["quantity"], amount))
    total = sum(amount for _, _, amount in lines)
    paid = sum(p["amount"] for p in hotel["payments"] if p["reservation_id"] == reservation_id)
    return {
        "code": reservation["code"],
        "lines": lines,
        "total": total,
        "paid": paid,
        "balance": total - paid,
    }


def print_bill(statement: dict) -> None:
    print(f"\n  Bill {statement['code']}")
    for label, quantity, amount in statement["lines"]:
        print(f"    {label:<40} x{quantity:<3} {fmt(amount):>14}")
    print(f"    {'Total':<45} {fmt(statement['total']):>14}")
    print(f"    {'Paid':<45} {fmt(statement['paid']):>14}")
    print(f"    {'Balance':<45} {fmt(statement['balance']):>14}\n")


# ---------------------------------------------------------------- sample data
def sample_hotel() -> dict:
    """The rooms and services used in the CP1 scenarios."""
    hotel = new_hotel()
    standard = add_category(hotel, "Standard", "Double room")
    deluxe = add_category(hotel, "Deluxe", "Larger room with a sea view")
    for number in ("101", "102", "103"):
        add_room(hotel, number, standard, 2, dinars("150"))
    for number in ("203", "204"):
        add_room(hotel, number, deluxe, 3, dinars("180"))
    add_extra(hotel, "Breakfast", dinars("15"))
    add_extra(hotel, "Airport transfer", dinars("40"))
    return hotel


# ---------------------------------------------------------------- terminal menu
def now() -> datetime:
    """The hotel's local time (the rules above take it as a parameter, so tests choose it)."""
    return datetime.now(HOTEL_TIME_ZONE).replace(tzinfo=None)


def ask(prompt: str) -> str:
    return input(f"  {prompt}: ").strip()


def ask_date(prompt: str) -> date:
    return date.fromisoformat(ask(f"{prompt} (YYYY-MM-DD)"))


def ask_int(prompt: str) -> int:
    text = ask(prompt)
    if not text.isdigit():
        raise ValueError(f"'{text}' is not a whole number.")
    return int(text)


def menu_guests(hotel: dict) -> None:
    found = find_guests(hotel, ask("Search (name, document, phone or e-mail)"))
    for g in found:
        name = f"{g['first_name']} {g['last_name']}"
        print(f"  #{g['id']} {name} - {g['id_doc_type']} {g['id_doc_number']}")
    if not found and ask("Nobody found. Register a new guest? (y/n)").lower() == "y":
        guest_id = register_guest(
            hotel,
            ask("First name"),
            ask("Last name"),
            ask("Document (CIN/PASSPORT)"),
            ask("Document number"),
            ask("Phone"),
            ask("E-mail"),
        )
        print(f"  Registered guest #{guest_id}.")


def menu_free_rooms(hotel: dict) -> None:
    rooms = available_rooms(hotel, ask_date("Arrival"), ask_date("Departure"))
    print("  Free rooms:", ", ".join(rooms) or "none")


def menu_book(hotel: dict) -> None:
    guest_id = ask_int("Guest id")
    arrival, departure = ask_date("Arrival"), ask_date("Departure")
    print("  Free rooms:", ", ".join(available_rooms(hotel, arrival, departure)) or "none")
    rooms = []
    for number in ask("Room numbers, separated by commas").split(","):
        adults = ask_int(f"Adults in room {number.strip()}")
        rooms.append((number.strip(), adults, 0))
    reservation_id = book(hotel, guest_id, arrival, departure, rooms)
    code = hotel["reservations"][reservation_id]["code"]
    print(f"  Booked: reservation #{reservation_id} ({code}).")


def menu_list(hotel: dict) -> None:
    for r in hotel["reservations"].values():
        guest = hotel["guests"][r["guest_id"]]
        rooms = ", ".join(line["room"] for line in r["rooms"])
        print(
            f"  #{r['id']} {r['code']} {guest['last_name']:<12} "
            f"{r['arrival']} -> {r['departure']}  rooms {rooms:<8} {r['status']}"
        )


def menu_change(hotel: dict) -> None:
    change_dates(
        hotel, ask_int("Reservation id"), ask_date("New arrival"), ask_date("New departure")
    )
    print("  Dates changed.")


def menu_cancel(hotel: dict) -> None:
    fee = cancel(hotel, ask_int("Reservation id"), now())
    print(f"  Cancelled. Fee: {fmt(fee)}")


def menu_check_in(hotel: dict) -> None:
    check_in(hotel, ask_int("Reservation id"), now().date())
    print("  Checked in.")


def menu_charge(hotel: dict) -> None:
    reservation_id = ask_int("Reservation id")
    for extra in hotel["extras"].values():
        print(f"  {extra['id']}. {extra['name']} ({fmt(extra['unit_price'])})")
    charge_extra(hotel, reservation_id, ask_int("Service"), ask_int("Quantity"), now().date())
    print("  Charged.")


def menu_pay(hotel: dict) -> None:
    reservation_id = ask_int("Reservation id")
    amount = dinars(ask("Amount in DT"))
    record_payment(hotel, reservation_id, amount, ask("Method (CASH/CARD/TRANSFER)").upper())
    print("  Payment recorded.")


def menu_bill(hotel: dict) -> None:
    print_bill(bill(hotel, ask_int("Reservation id")))


def menu_check_out(hotel: dict) -> None:
    print_bill(check_out(hotel, ask_int("Reservation id")))


def menu_maintenance(hotel: dict) -> None:
    room = ask("Room")
    start, end = ask_date("From"), ask_date("Until (first day open again)")
    close_for_maintenance(hotel, room, start, end, ask("Reason"))
    print(f"  Room {room} closed.")


# Menu number -> (label, function): a dict of tuples is the whole menu.
MENU = {
    "1": ("Find or register a guest", menu_guests),
    "2": ("Free rooms for dates", menu_free_rooms),
    "3": ("Book a stay", menu_book),
    "4": ("List reservations", menu_list),
    "5": ("Change the dates", menu_change),
    "6": ("Cancel a reservation", menu_cancel),
    "7": ("Check in", menu_check_in),
    "8": ("Charge an extra service", menu_charge),
    "9": ("Record a deposit or payment", menu_pay),
    "10": ("Show the bill", menu_bill),
    "11": ("Check out", menu_check_out),
    "12": ("Close a room for maintenance", menu_maintenance),
}


def main() -> None:
    hotel = sample_hotel()
    while True:
        print("\nHotel - procedural prototype (CP2)")
        for key, (label, _) in MENU.items():
            print(f"  {key:>2}. {label}")
        print("   0. Quit")
        choice = ask("Choice")
        if choice == "0":
            break
        if choice not in MENU:
            print("  Unknown choice.")
            continue
        try:
            MENU[choice][1](hotel)
        except ValueError as error:  # BR12: refused and clearly explained
            print(f"  Refused: {error}")


if __name__ == "__main__":
    main()

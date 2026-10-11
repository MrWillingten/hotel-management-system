"""Fictional demonstration data: `python -m hotel seed --demo`.

Everything is created through the normal services, with the same validation
and audit trail as data typed by a receptionist. All names, documents and
contact details are invented.
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from hotel.bootstrap import Services, build_services
from hotel.domain.actor import Actor
from hotel.domain.billing import PaymentMethod, PercentDiscount
from hotel.domain.clock import FixedClock
from hotel.domain.enums import Role
from hotel.domain.errors import BusinessRuleViolation, HotelError
from hotel.domain.guests import GuestDetails, search_key
from hotel.domain.money import Money
from hotel.domain.paging import PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import RoomRequest
from hotel.domain.rooms import Housekeeping
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxBase

DEMO_FLAG = "demo_data"

CATEGORIES = (
    (
        "Standard",
        "Double or twin room, city view",
        2,
        120,
        ["101", "102", "103", "104", "105", "106"],
    ),
    (
        "Deluxe",
        "Larger room with a sea view and a balcony",
        2,
        180,
        ["201", "202", "203", "204", "205", "206"],
    ),
    ("Family", "Two connected rooms for up to four guests", 4, 220, ["301", "302"]),
    ("Suite", "Living room, sea view and a private terrace", 4, 320, ["401", "402", "403"]),
)
FIRST_NAMES = (
    "Amira",
    "Youssef",
    "Mariem",
    "Karim",
    "Salma",
    "Sami",
    "Ines",
    "Mehdi",
    "Nour",
    "Aziz",
    "Hélène",
    "Julien",
    "Camille",
    "Lucas",
    "Giulia",
    "Marco",
    "Anna",
    "Jonas",
    "Emma",
    "Liam",
)
LAST_NAMES = (
    "Ben Salah",
    "Trabelsi",
    "Gharbi",
    "Haddad",
    "Jaziri",
    "Mansouri",
    "Bouazizi",
    "Chaabane",
    "Dupont",
    "Martin",
    "Rossi",
    "Schneider",
    "Novak",
    "Smith",
    "García",
    "Kowalski",
)
FOREIGN_COUNTRIES = ("FR", "IT", "DE", "GB", "ES", "PL", "BE", "DZ", "LY", "CA")
NOTES = (
    "",
    "",
    "",
    "Prefers a high floor",
    "Allergic to feathers",
    "Late arrival usual",
    "Business traveller, needs a desk",
)


EXTRAS = (
    ("Breakfast", 15),
    ("Dinner", 35),
    ("Airport transfer", 40),
    ("Laundry", 12),
    ("Minibar", 8),
    ("Spa access", 60),
)
HISTORY_DAYS = 7  # the demo replays the last week, so it has stays, bills and invoices
MAINTENANCE_ROOM = "105"


@dataclass
class DemoResult:
    accounts: dict[str, str] = field(default_factory=dict)  # username -> password (shown once)
    rooms: int = 0
    guests: int = 0
    reservations: int = 0
    invoices: int = 0


def _demo_password() -> str:
    return "demo-" + secrets.token_urlsafe(9)


def seed_demo(services: Services, *, guests: int = 40, seed: int = 2026) -> DemoResult:
    """Fill an empty hotel with fictional data. Refuses if rooms or guests already exist."""
    system = Actor.system("seed")
    with services.uow_factory() as uow:
        if uow.rooms.list() or uow.guests.search("", _first_page()).total:
            raise BusinessRuleViolation("demo.not_empty")
    result = DemoResult()
    # The generator is seeded so every demo database looks the same; it only
    # invents names and phone numbers, never anything security-related.
    rng = random.Random(seed)  # noqa: S311  # nosec B311

    # Everything goes through the normal services, but with a clock that starts
    # a week ago and is moved forward day by day ("replaying" the week).
    real_now = services.clock.now()
    clock = FixedClock(real_now - timedelta(days=HISTORY_DAYS), services.clock.hotel_tz)
    services = build_services(services.settings, clock=clock)

    manager = _demo_account(services, system, result, "demo.manager", "Demo Manager", Role.MANAGER)
    boss = Actor(manager) if manager else system
    _demo_account(
        services, system, result, "demo.reception", "Demo Receptionist", Role.RECEPTIONIST
    )

    rooms = services.rooms
    for name, description, capacity, rate, numbers in CATEGORIES:
        category = rooms.create_category(boss, name=name, description=description)
        for number in numbers:
            rooms.create_room(
                boss,
                number=number,
                category_id=category.id,
                capacity=capacity,
                nightly_rate=Money.from_dinars(rate),
            )
            result.rooms += 1
    _demo_catalogue(services, boss)

    used_documents: set[str] = set()
    for i in range(guests):
        details = _fictional_guest(rng, i, used_documents)
        guest = services.guests.register(system, details, confirm_duplicate=True)
        if i % 9 == 4:
            services.guests.set_flags(
                system, guest.id, version=guest.version, is_vip=True, do_not_rent=False
            )
        if i == guests - 1:
            services.guests.set_flags(
                boss,
                guest.id,
                version=guest.version,
                is_vip=False,
                do_not_rent=True,
                reason="Left without paying (demo)",
            )
        result.guests += 1

    _demo_history(services, clock, boss, rng, result)
    clock.advance(real_now - clock.now())  # back to the present
    today = services.clock.today()
    room_105 = next(o.room for o in rooms.list_rooms(boss) if o.room.number == MAINTENANCE_ROOM)
    rooms.schedule_maintenance(
        boss,
        room_105.id,
        first_night=today,
        reopens_on=today + timedelta(days=3),
        reason="Air conditioning repair",
    )
    result.reservations += _demo_reservations(services, system, rng)

    with services.uow_factory() as uow:
        uow.settings.set(DEMO_FLAG, "1")
    return result


def _demo_catalogue(services: Services, boss: Actor) -> None:
    for name, price in EXTRAS:
        services.extras.create(boss, name=name, unit_price=Money.from_dinars(price))
    # Example rates only: check them against current Tunisian regulations.
    taxes = services.hotel_settings
    taxes.create_tax_rule(boss, PercentTax(name="VAT", rate_bp=700))
    taxes.create_tax_rule(
        boss, PercentTax(name="VAT on services", rate_bp=1900, applies_to=TaxBase.SERVICES)
    )
    taxes.create_tax_rule(
        boss, PerAdultNightTax(name="Tourist tax", amount_per=Money.from_dinars(3))
    )


def _at(clock: FixedClock, hour: int) -> None:
    """Move the demo clock forward to `hour` o'clock (hotel time), never backwards."""
    local = datetime.combine(clock.today(), time(hour), tzinfo=clock.hotel_tz)
    if local < clock.now():
        local += timedelta(days=1)
    clock.advance(local - clock.now())


def _demo_history(
    services: Services, clock: FixedClock, boss: Actor, rng: random.Random, result: DemoResult
) -> None:
    """Replay the last week: walk-ins check in, charge extras, pay and check out."""
    desk = Actor.system("seed")
    extras = {e.name: e for e in services.extras.catalogue(desk)}
    guests = [
        g
        for g in services.guests.search(desk, "", PageRequest(per_page=100)).items
        if not g.do_not_rent
    ]
    if not guests:
        return
    for day in range(HISTORY_DAYS):
        _at(clock, 11)  # morning: departures
        for stay in services.front_desk.day(desk).departures:
            bill = services.billing.bill(desk, stay.id)
            # Exactly one guest leaves something unpaid, so the dashboard has a case.
            if bill.balance.millimes > 0 and result.invoices != 2:
                method = rng.choice([PaymentMethod.CARD, PaymentMethod.CASH])
                services.billing.record_payment(desk, stay.id, amount=bill.balance, method=method)
            services.invoices.check_out(desk, stay.id, version=stay.version)
            result.invoices += 1
        if day < HISTORY_DAYS - 1:  # today's rooms stay "to clean" for the demo
            for room in services.front_desk.day(desk).to_clean:
                services.rooms.set_housekeeping(desk, room.id, Housekeeping.CLEAN)

        _at(clock, 15)  # afternoon: arrivals
        today = clock.today()
        no_show = None
        for arrival in range(rng.randint(2, 4)):
            period = StayPeriod(today, today + timedelta(days=rng.randint(1, 4)))
            free = [
                r
                for r in services.reservations.find_available_rooms(desk, period)
                if r.number != MAINTENANCE_ROOM
            ]
            if not free:
                break
            room = rng.choice(free)
            adults = rng.randint(1, min(2, room.capacity))
            reservation = services.reservations.create(
                desk,
                guest_id=rng.choice(guests).id,
                period=period,
                rooms=[RoomRequest(room.id, adults)],
            )
            result.reservations += 1
            if day == 2 and arrival == 0:  # one guest never comes (recorded tonight)
                no_show = reservation
                continue
            if rng.random() < 0.4:  # a 30 % deposit paid by transfer before arriving
                deposit = reservation.accommodation_total.percent(3_000)
                services.billing.record_payment(
                    desk, reservation.id, amount=deposit, method=PaymentMethod.TRANSFER
                )
            reservation = services.reservations.check_in(
                desk, reservation.id, version=reservation.version
            )
            if day == 4 and arrival == 0:
                services.billing.grant_discount(
                    boss,
                    PercentDiscount(
                        reservation_id=reservation.id, reason="Returning guest", rate_bp=1000
                    ),
                )
            services.extras.charge(
                desk, reservation.id, extra_id=extras["Breakfast"].id, quantity=adults
            )
            extra = rng.choice(["Dinner", "Airport transfer", "Laundry", "Minibar", "Spa access"])
            services.extras.charge(
                desk, reservation.id, extra_id=extras[extra].id, quantity=rng.randint(1, 2)
            )
        if no_show is not None:
            _at(clock, 22)
            services.reservations.record_no_show(desk, no_show.id, version=no_show.version)
            result.invoices += 1
        _at(clock, 8)  # the next morning


def _demo_reservations(services: Services, system: Actor, rng: random.Random) -> int:
    """About two dozen bookings over the next three weeks, a few of them cancelled."""
    today = services.clock.today()
    rooms = [o.room for o in services.rooms.list_rooms(system) if o.room.in_service]
    guests = [
        g
        for g in services.guests.search(system, "", PageRequest(per_page=100)).items
        if not g.do_not_rent
    ]
    created = 0
    if not rooms or not guests:
        return created
    for attempt in range(40):
        room = rng.choice(rooms)
        arrival = today + timedelta(days=rng.randrange(0, 21))
        period = StayPeriod(arrival, arrival + timedelta(days=rng.randrange(1, 6)))
        try:
            reservation = services.reservations.create(
                system,
                guest_id=rng.choice(guests).id,
                period=period,
                rooms=[RoomRequest(room.id, rng.randint(1, room.capacity))],
            )
        except HotelError:
            continue  # that room was already taken: try another combination
        created += 1
        if attempt % 11 == 5 and arrival > today + timedelta(days=3):
            services.reservations.cancel(system, reservation.id, version=reservation.version)
    return created


def _demo_account(
    services: Services, system: Actor, result: DemoResult, username: str, full_name: str, role: Role
):
    with services.uow_factory() as uow:
        if uow.users.get_by_username(username) is not None:
            return None
    password = _demo_password()
    user = services.users.create_user(
        system, username=username, full_name=full_name, role=role, temporary_password=password
    )
    # Demo accounts may sign in straight away during a presentation.
    with services.uow_factory() as uow:
        stored = uow.users.get(user.id)
        stored.must_change_password = False
        uow.users.update(stored)
    result.accounts[username] = password
    return stored


def _first_page() -> PageRequest:
    return PageRequest(per_page=1)


_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"


def _fictional_guest(rng: random.Random, index: int, used_documents: set[str]) -> GuestDetails:
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    tunisian = index % 3 != 0
    while True:
        if tunisian:
            number = f"{rng.randrange(10**7, 10**8):08d}"
        else:
            number = f"{rng.choice(_LETTERS)}{rng.choice(_LETTERS)}{rng.randrange(10**6, 10**7)}"
        if number not in used_documents:
            used_documents.add(number)
            break
    if tunisian:
        phone = f"+216 {rng.choice('2459')}{rng.randrange(1_000_000, 9_999_999)}"
    else:
        code = rng.choice(["33", "39", "49", "44", "34"])
        phone = f"+{code} {rng.randrange(600_000_000, 799_999_999)}"
    local = search_key(f"{first}.{last}").replace(" ", "")
    return GuestDetails(
        first_name=first,
        last_name=last,
        id_doc_type="CIN" if tunisian else "PASSPORT",
        id_doc_number=number,
        nationality="TN" if tunisian else rng.choice(FOREIGN_COUNTRIES),
        phone=phone,
        email=f"{local}{index}@example.com" if rng.random() < 0.7 else "",
        notes=rng.choice(NOTES),
    )


def is_demo(services: Services) -> bool:
    with services.uow_factory() as uow:
        return uow.settings.get(DEMO_FLAG) == "1"

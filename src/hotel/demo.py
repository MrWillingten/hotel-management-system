"""Fictional demonstration data: `python -m hotel seed --demo`.

Everything is created through the normal services, with the same validation
and audit trail as data typed by a receptionist. All names, documents and
contact details are invented.
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta

import phonenumbers

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
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxBase, TaxPayers

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
HISTORY_DAYS = 120  # about four months of replayed activity, so reports and charts have data
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


def seed_demo(
    services: Services, *, guests: int = 40, seed: int = 2026, history_days: int = HISTORY_DAYS
) -> DemoResult:
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
    # `history_days` ago and is moved forward day by day ("replaying" them).
    # The replay starts at 07:00 on its first day and ends yesterday evening, so
    # no record is ever dated after the real present.
    real_now = services.clock.now()
    tz = services.clock.hotel_tz
    first_day = services.clock.today() - timedelta(days=history_days)
    clock = FixedClock(datetime.combine(first_day, time(7), tzinfo=tz), tz)
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
    _demo_prices(services, boss, history_days)

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

    _demo_history(services, clock, boss, rng, result, history_days)
    clock.advance(real_now - clock.now())  # back to the present
    services.night_audit.catch_up(boss)
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
    # Example only (story 6.16): a tourist tax that concerns foreign guests.
    taxes.create_tax_rule(
        boss,
        PerAdultNightTax(
            name="Tourist tax", amount_per=Money.from_dinars(3), payers=TaxPayers.FOREIGN
        ),
    )


def _at(clock: FixedClock, hour: int) -> None:
    """Move the demo clock forward to `hour` o'clock (hotel time), never backwards."""
    local = datetime.combine(clock.today(), time(hour), tzinfo=clock.hotel_tz)
    if local < clock.now():
        local += timedelta(days=1)
    clock.advance(local - clock.now())


def _demo_prices(services: Services, boss: Actor, history_days: int) -> None:
    """A 10 % weekend surcharge and a high season in the middle of the replayed months."""
    settings = services.hotel_settings.get(boss)
    services.hotel_settings.update(boss, replace(settings, weekend_surcharge_bp=1_000))
    start = services.clock.today()
    first = start + timedelta(days=history_days // 4)
    last = start + timedelta(days=history_days // 2)
    for category in services.rooms.list_categories(boss):
        base = next(rate for name, _, _, rate, _ in CATEGORIES if name == category.name)
        services.rooms.add_rate_period(
            boss,
            category_id=category.id,
            name="High season",
            first_night=first,
            last_night=last,
            nightly_rate=Money.from_dinars(base * 13 // 10),
        )


def _demo_history(
    services: Services,
    clock: FixedClock,
    boss: Actor,
    rng: random.Random,
    result: DemoResult,
    history_days: int,
) -> None:
    """Replay the past days: bookings, check-ins, extras, payments, check-outs."""
    desk = Actor.system("seed")
    extras = {e.name: e for e in services.extras.catalogue(desk)}
    guests = [
        g
        for g in services.guests.search(desk, "", PageRequest(per_page=100)).items
        if not g.do_not_rent
    ]
    if not guests:
        return
    for day in range(history_days):
        if day:
            services.night_audit.run(boss)  # 08:00: close yesterday
        _at(clock, 11)  # morning: departures
        for stay in services.front_desk.day(desk).departures:
            bill = services.billing.bill(desk, stay.id)
            # Exactly one guest leaves something unpaid, so the dashboard has a case.
            if bill.balance.millimes > 0 and result.invoices != 2:
                method = rng.choice([PaymentMethod.CARD, PaymentMethod.CASH])
                services.billing.record_payment(desk, stay.id, amount=bill.balance, method=method)
            services.invoices.check_out(desk, stay.id, version=stay.version)
            result.invoices += 1
        if day < history_days - 1:  # today's rooms stay "to clean" for the demo
            for room in services.front_desk.day(desk).to_clean:
                services.rooms.set_housekeeping(desk, room.id, Housekeeping.INSPECTED)

        _at(clock, 12)  # the phone rings: bookings for later, some cancelled
        today = clock.today()
        if rng.random() < 0.5:
            _advance_booking(services, desk, rng, guests, today, result)

        _at(clock, 15)  # afternoon: arrivals (booked earlier, plus walk-ins)
        no_show = None
        for expected in services.front_desk.day(desk).arrivals:
            _arrive(services, desk, boss, rng, extras, expected, result, discount=False)
        weekend = today.weekday() in (4, 5)  # Friday and Saturday arrivals are busier
        for walk_in in range(rng.randint(2, 4) if weekend else rng.randint(0, 2)):
            period = StayPeriod(today, today + timedelta(days=rng.randint(1, 4)))
            reservation = _book(services, desk, rng, guests, period)
            if reservation is None:
                break
            result.reservations += 1
            if day == 2 and walk_in == 0 and no_show is None:  # one guest never comes
                no_show = reservation
                continue
            _arrive(services, desk, boss, rng, extras, reservation, result, discount=day == 4)
        if no_show is not None:
            _at(clock, 22)
            services.reservations.record_no_show(desk, no_show.id, version=no_show.version)
            result.invoices += 1
        if day < history_days - 1:
            _at(clock, 8)  # the next morning


def _book(services, desk, rng, guests, period):
    free = [
        r
        for r in services.reservations.find_available_rooms(desk, period)
        if r.number != MAINTENANCE_ROOM
    ]
    if not free:
        return None
    room = rng.choice(free)
    return services.reservations.create(
        desk,
        guest_id=rng.choice(guests).id,
        period=period,
        rooms=[RoomRequest(room.id, rng.randint(1, min(2, room.capacity)))],
    )


def _advance_booking(services, desk, rng, guests, today, result) -> None:
    arrival = today + timedelta(days=rng.randint(3, 20))
    reservation = _book(
        services,
        desk,
        rng,
        guests,
        StayPeriod(arrival, arrival + timedelta(days=rng.randint(2, 5))),
    )
    if reservation is None:
        return
    result.reservations += 1
    if rng.random() < 0.4:  # a 30 % deposit paid by transfer
        services.billing.record_payment(
            desk,
            reservation.id,
            amount=reservation.accommodation_total.percent(3_000),
            method=PaymentMethod.TRANSFER,
        )
    if rng.random() < 0.15:  # a change of plans, early enough to be free
        services.reservations.cancel(desk, reservation.id, version=reservation.version)


def _arrive(services, desk, boss, rng, extras, reservation, result, *, discount: bool) -> None:
    """Check the guest in and charge a breakfast and one other extra."""
    reservation = services.reservations.check_in(desk, reservation.id, version=reservation.version)
    if discount:
        services.billing.grant_discount(
            boss,
            PercentDiscount(reservation_id=reservation.id, reason="Returning guest", rate_bp=1000),
        )
    adults = reservation.rooms[0].adults
    services.extras.charge(desk, reservation.id, extra_id=extras["Breakfast"].id, quantity=adults)
    extra = rng.choice(["Dinner", "Airport transfer", "Laundry", "Minibar", "Spa access"])
    services.extras.charge(
        desk, reservation.id, extra_id=extras[extra].id, quantity=rng.randint(1, 2)
    )


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
    nationality = "TN" if tunisian else rng.choice(FOREIGN_COUNTRIES)
    local = search_key(f"{first}.{last}").replace(" ", "")
    return GuestDetails(
        first_name=first,
        last_name=last,
        id_doc_type="CIN" if tunisian else "PASSPORT",
        id_doc_number=number,
        nationality=nationality,
        phone=_fictional_phone(rng, nationality),
        email=f"{local}{index}@example.com" if rng.random() < 0.7 else "",
        notes=rng.choice(NOTES),
    )


def _fictional_phone(rng: random.Random, region: str) -> str:
    """A mobile number that is valid in that country but invented.

    Google's example number for the country keeps a real prefix and length;
    only its last four digits are drawn at random (and checked again).
    """
    example = phonenumbers.example_number_for_type(region, phonenumbers.PhoneNumberType.MOBILE)
    national = str(example.national_number)
    for _ in range(20):
        candidate = phonenumbers.parse(
            f"+{example.country_code}{national[:-4]}{rng.randrange(10_000):04d}"
        )
        if phonenumbers.is_valid_number(candidate):
            example = candidate
            break
    return phonenumbers.format_number(example, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


def is_demo(services: Services) -> bool:
    with services.uow_factory() as uow:
        return uow.settings.get(DEMO_FLAG) == "1"

"""The scenarios of the project brief (CP1, section 2.6), run on the prototype.

    python prototype/scenarios.py

Each function builds a fresh sample hotel, plays the scenario and checks the
expected result with `assert`. The same functions are run by the test suite
(tests/unit/test_prototype.py).
"""

from __future__ import annotations

from datetime import date, datetime

from hotel_prototype import (
    available_rooms,
    bill,
    book,
    cancel,
    change_dates,
    charge_extra,
    check_in,
    check_out,
    close_for_maintenance,
    dinars,
    find_guests,
    fmt,
    nights,
    no_show,
    overlaps,
    record_payment,
    register_guest,
    room_status,
    sample_hotel,
)

BREAKFAST, TRANSFER = 1, 2  # ids of the sample extra services


def refused(action, *args) -> str:
    """Run an action that must be refused; return the explanation (BR12)."""
    try:
        action(*args)
    except ValueError as error:
        return str(error)
    raise AssertionError(f"{action.__name__} should have been refused")


def guest(hotel: dict) -> int:
    return register_guest(hotel, "Amira", "Ben Salah", "CIN", "07123456", "+216 20 123 456")


def scenario_1_maintenance() -> str:
    """Room 204 (Deluxe, 180 DT) closed for three days: no reservation can cover them."""
    hotel = sample_hotel()
    close_for_maintenance(hotel, "204", date(2027, 7, 3), date(2027, 7, 6), "Painting")
    why = refused(book, hotel, guest(hotel), date(2027, 7, 4), date(2027, 7, 5), [("204", 2, 0)])
    assert "204" not in available_rooms(hotel, date(2027, 7, 3), date(2027, 7, 6))
    assert room_status(hotel, "204", date(2027, 7, 4)) == "unavailable"
    # The day it opens again can be booked (the end date is not closed).
    book(hotel, 1, date(2027, 7, 6), date(2027, 7, 7), [("204", 2, 0)])
    return why


def scenario_2_returning_guest() -> str:
    """A returning guest calls: the existing record is found, not duplicated."""
    hotel = sample_hotel()
    guest(hotel)
    found = find_guests(hotel, "ben salah")
    assert [g["id"] for g in found] == [1]
    why = refused(register_guest, hotel, "Amira", "Ben Salah", "CIN", "07123456")
    assert len(hotel["guests"]) == 1
    return why


def scenario_3_conflict() -> str:
    """Request 10-15 July while the room is booked 12-14 July: refused, alternatives given."""
    hotel = sample_hotel()
    amira = guest(hotel)
    book(hotel, amira, date(2027, 7, 12), date(2027, 7, 14), [("101", 2, 0)])
    other = register_guest(hotel, "Lucas", "Dupont", "PASSPORT", "18AB12345")
    why = refused(book, hotel, other, date(2027, 7, 10), date(2027, 7, 15), [("101", 2, 0)])
    assert "Free rooms: 102, 103, 203, 204" in why
    # Arriving on the day the other guest leaves is allowed (BR13).
    book(hotel, other, date(2027, 7, 14), date(2027, 7, 15), [("101", 2, 0)])
    return why


def scenario_4_extend() -> str:
    """Extend a stay from 3 to 5 nights: allowed only if the room is free for the extra nights."""
    hotel = sample_hotel()
    amira = guest(hotel)
    stay = book(hotel, amira, date(2027, 7, 1), date(2027, 7, 4), [("102", 2, 0)])
    change_dates(hotel, stay, date(2027, 7, 1), date(2027, 7, 6))  # 3 -> 5 nights
    assert bill(hotel, stay)["total"] == dinars("750")
    other = register_guest(hotel, "Lucas", "Dupont", "PASSPORT", "18AB12345")
    book(hotel, other, date(2027, 7, 6), date(2027, 7, 8), [("102", 1, 0)])
    return refused(change_dates, hotel, stay, date(2027, 7, 1), date(2027, 7, 7))


def scenario_5_and_6_stay_with_services() -> str:
    """Arrival, 4 nights, 3 breakfasts and 1 airport transfer, departure: all on the bill."""
    hotel = sample_hotel()
    stay = book(hotel, guest(hotel), date(2027, 7, 1), date(2027, 7, 5), [("103", 1, 0)])
    why = refused(charge_extra, hotel, stay, BREAKFAST, 1, date(2027, 7, 1))  # not arrived yet
    check_in(hotel, stay, date(2027, 7, 1))
    charge_extra(hotel, stay, BREAKFAST, 3, date(2027, 7, 2))
    charge_extra(hotel, stay, TRANSFER, 1, date(2027, 7, 5))
    statement = check_out(hotel, stay)
    labels = [label for label, _, _ in statement["lines"]]
    assert labels == ["Room 103 - nights at 150.000 DT", "Breakfast", "Airport transfer"]
    assert statement["total"] == dinars("600") + dinars("45") + dinars("40")
    return why


def scenario_7_bill() -> str:
    """3 nights x 150 DT, 80 DT of services, 100 DT deposit: total 530 DT, balance 430 DT."""
    hotel = sample_hotel()
    stay = book(hotel, guest(hotel), date(2027, 7, 1), date(2027, 7, 4), [("101", 2, 0)])
    record_payment(hotel, stay, dinars("100"), "CARD")  # deposit before arrival (BR10)
    check_in(hotel, stay, date(2027, 7, 1))
    charge_extra(hotel, stay, TRANSFER, 2, date(2027, 7, 1))  # 2 x 40 DT = 80 DT
    statement = bill(hotel, stay)
    assert statement["total"] == dinars("530")
    assert statement["paid"] == dinars("100")
    assert statement["balance"] == dinars("430")
    return f"total {fmt(statement['total'])}, balance {fmt(statement['balance'])}"


def scenario_cancellation_fee() -> str:
    """BR11: 20 % fee under 48 hours before arrival at 14:00; exactly 48 hours is free."""
    hotel = sample_hotel()
    amira = guest(hotel)
    early = book(hotel, amira, date(2027, 7, 10), date(2027, 7, 12), [("101", 2, 0)])
    late = book(hotel, amira, date(2027, 7, 10), date(2027, 7, 12), [("102", 2, 0)])
    assert cancel(hotel, early, datetime(2027, 7, 8, 14, 0)) == 0  # exactly 48:00
    fee = cancel(hotel, late, datetime(2027, 7, 8, 14, 1))  # 47:59 before
    assert fee == dinars("60")  # 20 % of 2 x 150 DT
    assert bill(hotel, late)["total"] == dinars("60")
    return f"fee {fmt(fee)}"


def scenario_no_show_and_life_cycle() -> str:
    """Decision F and BR16: a no-show after the arrival time; no check-out without check-in."""
    hotel = sample_hotel()
    stay = book(hotel, guest(hotel), date(2027, 7, 10), date(2027, 7, 11), [("203", 2, 0)])
    why = refused(check_out, hotel, stay)
    assert no_show(hotel, stay, datetime(2027, 7, 10, 23, 0)) == dinars("36")
    assert "203" in available_rooms(hotel, date(2027, 7, 10), date(2027, 7, 11))
    return why


def scenario_price_locked() -> str:
    """BR20: a later price change never alters an existing reservation."""
    hotel = sample_hotel()
    stay = book(hotel, guest(hotel), date(2027, 8, 1), date(2027, 8, 3), [("204", 2, 0)])
    hotel["rooms"]["204"]["nightly_rate"] = dinars("220")  # the manager raises the price
    assert bill(hotel, stay)["total"] == dinars("360")  # still 2 x 180 DT
    assert nights(date(2027, 8, 1), date(2027, 8, 3)) == 2
    assert not overlaps(date(2027, 8, 1), date(2027, 8, 3), date(2027, 8, 3), date(2027, 8, 5))
    return "2 nights still at 180.000 DT"


SCENARIOS = [
    scenario_1_maintenance,
    scenario_2_returning_guest,
    scenario_3_conflict,
    scenario_4_extend,
    scenario_5_and_6_stay_with_services,
    scenario_7_bill,
    scenario_cancellation_fee,
    scenario_no_show_and_life_cycle,
    scenario_price_locked,
]

if __name__ == "__main__":
    for scenario in SCENARIOS:
        detail = scenario()
        print(f"PASS  {scenario.__doc__.splitlines()[0]}\n      -> {detail}")
    print(f"\nAll {len(SCENARIOS)} scenarios passed.")

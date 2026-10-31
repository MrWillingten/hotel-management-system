"""One search box in the top bar (story 7.7): code, room or guest, from any page.

The phone rings in the middle of something else and the guest gives a name, a
room number or a reservation code: the receptionist types it in one place and
lands on the right page (an occupied room opens the guest's stay). A plain GET
form and a redirect, no JavaScript.
"""

from __future__ import annotations

import re

from flask import Blueprint, redirect, request, url_for

from hotel.domain.paging import PageRequest
from hotel.domain.reservations import ReservationStatus
from hotel.persistence.repositories.reservations import ReservationFilter
from hotel.web.context import current_actor, services
from hotel.web.security import login_required

bp = Blueprint("search", __name__, url_prefix="/search")

RESERVATION_CODE = re.compile(r"R-\d{4}-\d{1,6}")
INVOICE_NUMBER = re.compile(r"F-\d{4}-\d{1,6}")


@bp.get("/")
@login_required
def go():
    actor = current_actor()
    text = request.args.get("q", "")[:50].strip()
    if not text:
        return redirect(url_for("dashboard.index"))
    upper = text.upper()
    if RESERVATION_CODE.fullmatch(upper):
        found = services().reservations.search(
            actor, ReservationFilter(query=upper), PageRequest(per_page=5)
        )
        exact = [r for r in found.items if r.code == upper]
        if exact:
            return redirect(url_for("reservations.detail", reservation_id=exact[0].id))
        return redirect(url_for("reservations.index", q=upper))
    if INVOICE_NUMBER.fullmatch(upper):
        return redirect(url_for("invoices.index", q=upper))
    for overview in services().rooms.list_rooms(actor):
        if overview.room.number == upper:
            # An occupied room: the caller wants the guest's stay, not the room's settings.
            staying = services().reservations.search(
                actor,
                ReservationFilter(status=ReservationStatus.CHECKED_IN),
                PageRequest(per_page=100),
            )
            for r in staying.items:
                if any(b.room_id == overview.room.id for b in r.current_rooms):
                    return redirect(url_for("reservations.detail", reservation_id=r.id))
            return redirect(url_for("rooms.detail", room_id=overview.room.id))
    return redirect(url_for("guests.index", q=text))

"""Reservations: search, book (choose -> review -> confirm), list and detail."""

from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _

from hotel.domain.errors import HotelError, ValidationError
from hotel.domain.paging import PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import ReservationStatus, RoomRequest
from hotel.persistence.repositories.reservations import ReservationFilter
from hotel.services.reservations import RoomUnavailableError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.formatting import money
from hotel.web.messages import message_for
from hotel.web.security import login_required

bp = Blueprint("reservations", __name__, url_prefix="/reservations")


# ---------------------------------------------------------------- helpers
def _period(data) -> StayPeriod:
    arrival = forms.calendar_date(data, "arrival")
    departure = forms.calendar_date(data, "departure")
    if departure <= arrival:
        raise ValidationError(
            "period.departure_not_after_arrival",
            fields={"departure": "period.departure_not_after_arrival"},
        )
    return StayPeriod(arrival, departure)


def _room_requests(data) -> list[RoomRequest]:
    """Selected rooms with their occupants: room=<id>, adults_<id>, children_<id>."""
    requests = []
    for raw in data.getlist("room")[:20]:
        if not raw.isdigit():
            continue
        room_id = int(raw)
        requests.append(
            RoomRequest(
                room_id,
                forms.integer(data, f"adults_{room_id}"),
                forms.integer(data, f"children_{room_id}", required=False) or 0,
            )
        )
    if not requests:
        raise ValidationError("reservation.no_room_selected")
    return requests


def _booking_page(errors=None, status=200, *, unavailable=None):
    """The "new reservation" page, rebuilt from the query string (or a failed POST)."""
    actor = current_actor()
    args = request.values
    guest_id = request.values.get("guest_id", type=int)
    today = services().clock.today()
    values = {
        "arrival": args.get("arrival", today.isoformat()),
        "departure": args.get("departure", (today + timedelta(days=1)).isoformat()),
        "guests": args.get("guests", "1"),
        "category": args.get("category", ""),
        "q": args.get("q", "")[:100],
        "room": args.get("room", ""),
    }
    errors = errors or forms.FormErrors()
    guest = rooms = None
    period = None
    if guest_id:
        try:
            guest = services().guests.get(actor, guest_id)
        except HotelError:
            guest = None
    matches = []
    if guest is None and values["q"]:
        matches = services().guests.search(actor, values["q"], PageRequest(per_page=8)).items
    if "arrival" in args:
        try:
            period = _period(args)
            rooms = services().reservations.find_available_rooms(
                actor,
                period,
                min_capacity=max(1, int(values["guests"]) if values["guests"].isdigit() else 1),
                category_id=args.get("category", type=int),
            )
        except HotelError as exc:
            errors.update(forms.FormErrors.from_error(exc))
    return render_template(
        "reservations/new.html",
        values=values,
        guest=guest,
        matches=matches,
        period=period,
        rooms=rooms,
        categories=services().rooms.list_categories(actor),
        errors=errors,
        unavailable=unavailable,
    ), status


# ---------------------------------------------------------------- pages
@bp.get("/")
@login_required
def index():
    args = request.args
    try:
        status = ReservationStatus(args.get("status", ""))
    except ValueError:
        status = None
    filters = ReservationFilter(
        query=args.get("q", "")[:50].strip(),
        status=status,
        arriving_from=_optional_date(args, "from"),
        arriving_until=_optional_date(args, "until"),
    )
    page = services().reservations.search(current_actor(), filters, forms.page_request(args))
    return render_template(
        "reservations/index.html", page=page, filters=filters, statuses=list(ReservationStatus)
    )


def _optional_date(args, name):
    try:
        return forms.calendar_date(args, name, required=False)
    except ValidationError:
        return None


@bp.get("/new")
@login_required
def new():
    return _booking_page()


@bp.post("/review")
@login_required
def review():
    """Step 2: check everything and show the exact price before anything is saved."""
    actor = current_actor()
    data = request.form
    try:
        guest_id = forms.integer(data, "guest_id")
        period = _period(data)
        rooms = _room_requests(data)
        quote = services().reservations.quote(actor, guest_id=guest_id, period=period, rooms=rooms)
    except RoomUnavailableError as exc:
        return _booking_page(forms.FormErrors.from_error(exc), 409, unavailable=exc)
    except HotelError as exc:
        return _booking_page(forms.FormErrors.from_error(exc), 400)
    return render_template(
        "reservations/review.html",
        quote=quote,
        guest=services().guests.get(actor, guest_id),
        notes=forms.text(data, "notes", max_length=500),
        policy_free_until=services().reservations.free_cancellation_until(period),
        form_token=services().form_tokens.issue(actor),
    )


@bp.post("/")
@login_required
def create():
    """Step 3: book. The one-time token makes a double click harmless."""
    actor = current_actor()
    data = request.form
    if not services().form_tokens.consume(actor, data.get("form_token")):
        flash(
            _("This form was already submitted. Check the reservation list before trying again."),
            "warning",
        )
        return redirect(url_for("reservations.index"))
    try:
        reservation = services().reservations.create(
            actor,
            guest_id=forms.integer(data, "guest_id"),
            period=_period(data),
            rooms=_room_requests(data),
            notes=forms.text(data, "notes", max_length=500),
        )
    except RoomUnavailableError as exc:
        return _booking_page(forms.FormErrors.from_error(exc), 409, unavailable=exc)
    except HotelError as exc:
        return _booking_page(forms.FormErrors.from_error(exc), 400)
    flash(_("Reservation %(code)s confirmed.", code=reservation.code), "success")
    return redirect(url_for("reservations.detail", reservation_id=reservation.id))


@bp.get("/<int:reservation_id>")
@login_required
def detail(reservation_id: int):
    reservation = services().reservations.get(current_actor(), reservation_id)
    return render_template(
        "reservations/detail.html",
        reservation=reservation,
        free_until=services().reservations.free_cancellation_until(reservation.period),
    )


# ---------------------------------------------------------------- changing
def _indexed_room_requests(data) -> list[RoomRequest]:
    """Edit form rows: room_<i>, adults_<i>, children_<i>; an empty room removes the row."""
    requests = []
    for index in range(10):
        raw = data.get(f"room_{index}", "")
        if not raw.isdigit():
            continue
        requests.append(
            RoomRequest(
                int(raw),
                forms.integer(data, f"adults_{index}"),
                forms.integer(data, f"children_{index}", required=False) or 0,
            )
        )
    if not requests:
        raise ValidationError("reservation.no_room_selected")
    return requests


def _edit_page(reservation, *, values=None, errors=None, quote=None, status=200):
    actor = current_actor()
    rooms = [o.room for o in services().rooms.list_rooms(actor) if o.room.in_service]
    return render_template(
        "reservations/edit.html",
        reservation=reservation,
        rooms=rooms,
        values=values,
        errors=errors or forms.FormErrors(),
        quote=quote,
        form_token=services().form_tokens.issue(actor) if quote else "",
    ), status


@bp.get("/<int:reservation_id>/edit")
@login_required
def edit(reservation_id: int):
    return _edit_page(services().reservations.get(current_actor(), reservation_id))


@bp.post("/<int:reservation_id>/edit")
@login_required
def edit_review(reservation_id: int):
    """Check the change and show the new price next to the old one."""
    actor = current_actor()
    data = request.form
    try:
        current, quote = services().reservations.preview_change(
            actor, reservation_id, period=_period(data), rooms=_indexed_room_requests(data)
        )
    except HotelError as exc:
        reservation = services().reservations.get(actor, reservation_id)
        return _edit_page(
            reservation,
            values=data,
            errors=forms.FormErrors.from_error(exc),
            status=409 if isinstance(exc, RoomUnavailableError) else 400,
        )
    return _edit_page(current, values=data, quote=quote)


@bp.post("/<int:reservation_id>/change")
@login_required
def change(reservation_id: int):
    actor = current_actor()
    data = request.form
    if not services().form_tokens.consume(actor, data.get("form_token")):
        flash(
            _("This form was already submitted. Check the reservation before trying again."),
            "warning",
        )
        return redirect(url_for("reservations.detail", reservation_id=reservation_id))
    try:
        services().reservations.modify(
            actor,
            reservation_id,
            version=forms.integer(data, "version"),
            period=_period(data),
            rooms=_indexed_room_requests(data),
        )
    except HotelError as exc:
        reservation = services().reservations.get(actor, reservation_id)
        return _edit_page(
            reservation, values=data, errors=forms.FormErrors.from_error(exc), status=409
        )
    flash(_("Reservation updated."), "success")
    return redirect(url_for("reservations.detail", reservation_id=reservation_id))


# ---------------------------------------------------------------- cancelling
@bp.route("/<int:reservation_id>/cancel", methods=["GET", "POST"])
@login_required
def cancel(reservation_id: int):
    actor = current_actor()
    reservations = services().reservations
    if request.method == "POST":
        if not services().form_tokens.consume(actor, request.form.get("form_token")):
            flash(
                _("This form was already submitted. Check the reservation before trying again."),
                "warning",
            )
            return redirect(url_for("reservations.detail", reservation_id=reservation_id))
        try:
            cancelled = reservations.cancel(
                actor, reservation_id, version=forms.integer(request.form, "version")
            )
        except HotelError as exc:
            flash(message_for(exc.code, exc.params), "danger")
        else:
            flash(
                _("Reservation cancelled. Fee: %(fee)s.", fee=money(cancelled.cancellation_fee)),
                "success",
            )
        return redirect(url_for("reservations.detail", reservation_id=reservation_id))
    reservation = reservations.get(actor, reservation_id)
    try:
        fee = reservations.cancellation_fee(actor, reservation_id)
        problem = None
    except HotelError as exc:
        fee, problem = None, message_for(exc.code, exc.params)
    return render_template(
        "reservations/cancel.html",
        reservation=reservation,
        fee=fee,
        problem=problem,
        free_until=reservations.free_cancellation_until(reservation.period),
        form_token=services().form_tokens.issue(actor),
    )

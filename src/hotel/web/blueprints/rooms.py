"""Rooms, categories and maintenance."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _

from hotel.domain.enums import Role
from hotel.domain.errors import HotelError
from hotel.domain.rooms import Housekeeping
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.messages import message_for
from hotel.web.removal import confirm_removal
from hotel.web.security import is_safe_redirect_target, login_required, roles_required

bp = Blueprint("rooms", __name__, url_prefix="/rooms")


def _room_fields(data) -> dict:
    return {
        "number": forms.text(data, "number", max_length=10),
        "category_id": forms.integer(data, "category_id"),
        "capacity": forms.integer(data, "capacity"),
        "nightly_rate": forms.money(data, "nightly_rate"),
        "notes": forms.text(data, "notes", max_length=500),
    }


@bp.get("/")
@login_required
def index():
    rooms = services().rooms
    actor = current_actor()
    category_id = request.args.get("category", type=int)  # None if missing or not a number
    archived = request.args.get("archived") == "1"
    return render_template(
        "rooms/index.html",
        rooms=rooms.list_rooms(actor, category_id=category_id, archived=archived),
        categories=rooms.list_categories(actor),
        category_id=category_id,
        archived=archived,
        archived_count=rooms.count_archived(actor),
    )


@bp.route("/new", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def create():
    errors, values = forms.FormErrors(), request.form
    categories = services().rooms.list_categories(current_actor())
    if request.method == "POST":
        try:
            room = services().rooms.create_room(current_actor(), **_room_fields(request.form))
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("Room %(number)s added.", number=room.number), "success")
            return redirect(url_for("rooms.detail", room_id=room.id))
    return render_template(
        "rooms/form.html", room=None, values=values, errors=errors, categories=categories
    ), (400 if errors else 200)


@bp.route("/<int:room_id>/edit", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def edit(room_id: int):
    actor = current_actor()
    errors = forms.FormErrors()
    overview = services().rooms.get_room(actor, room_id)
    values = request.form if request.method == "POST" else None
    if request.method == "POST":
        try:
            services().rooms.update_room(
                actor,
                room_id,
                version=forms.integer(request.form, "version"),
                in_service=forms.checkbox(request.form, "in_service"),
                **_room_fields(request.form),
            )
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("Changes saved."), "success")
            return redirect(url_for("rooms.detail", room_id=room_id))
    return render_template(
        "rooms/form.html",
        room=overview.room,
        values=values,
        errors=errors,
        categories=services().rooms.list_categories(actor),
    ), (400 if errors else 200)


@bp.get("/<int:room_id>")
@login_required
def detail(room_id: int):
    actor = current_actor()
    rooms = services().rooms
    return render_template(
        "rooms/detail.html",
        overview=rooms.get_room(actor, room_id),
        maintenance=rooms.maintenance_for_room(actor, room_id),
        today=services().clock.today(),
        errors=forms.FormErrors(),
        values={},
    )


@bp.post("/<int:room_id>/housekeeping")
@login_required
def housekeeping(room_id: int):
    """Story 4.9: dirty -> cleaned -> inspected (ready), or back to dirty."""
    try:
        state = Housekeeping(request.form.get("state", ""))
    except ValueError:
        state = None  # an unknown value changes nothing
    if state is not None:
        room = services().rooms.set_housekeeping(current_actor(), room_id, state)
        messages = {
            Housekeeping.DIRTY: _("Room %(number)s is marked to be cleaned.", number=room.number),
            Housekeeping.CLEAN: _(
                "Room %(number)s is cleaned and waits for its inspection.", number=room.number
            ),
            Housekeeping.INSPECTED: _(
                "Room %(number)s is ready for the next guest.", number=room.number
            ),
        }
        flash(messages[state], "success")
    target = request.form.get("next")
    if is_safe_redirect_target(target):
        return redirect(target)
    return redirect(url_for("rooms.detail", room_id=room_id))


@bp.post("/<int:room_id>/maintenance")
@roles_required(Role.MANAGER)
def schedule_maintenance(room_id: int):
    actor = current_actor()
    rooms = services().rooms
    data = request.form
    try:
        period = rooms.schedule_maintenance(
            actor,
            room_id,
            first_night=forms.calendar_date(data, "first_night"),
            reopens_on=forms.calendar_date(data, "reopens_on"),
            reason=forms.text(data, "reason", max_length=200),
        )
    except HotelError as exc:
        return render_template(
            "rooms/detail.html",
            overview=rooms.get_room(actor, room_id),
            maintenance=rooms.maintenance_for_room(actor, room_id),
            today=services().clock.today(),
            errors=forms.FormErrors.from_error(exc),
            values=data,
        ), 400
    flash(
        _(
            "Room closed from %(first)s; it reopens on %(reopens)s.",
            first=period.first_night.isoformat(),
            reopens=period.reopens_on.isoformat(),
        ),
        "success",
    )
    return redirect(url_for("rooms.detail", room_id=room_id))


@bp.post("/maintenance/<int:maintenance_id>/cancel")
@roles_required(Role.MANAGER)
def cancel_maintenance(maintenance_id: int):
    room_id = forms.integer(request.form, "room_id")
    try:
        ended = services().rooms.cancel_maintenance(current_actor(), maintenance_id)
    except HotelError as exc:
        flash(message_for(exc.code, exc.params), "danger")
    else:
        flash(
            _("Maintenance ended: the room is available again from today.")
            if ended
            else _("Maintenance cancelled."),
            "success",
        )
    return redirect(url_for("rooms.detail", room_id=room_id))


@bp.route("/categories", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def categories():
    actor = current_actor()
    errors, values = forms.FormErrors(), {}
    if request.method == "POST":
        data = request.form
        values = data
        try:
            category_id = forms.integer(data, "id", required=False)
            name = forms.text(data, "name", max_length=50)
            description = forms.text(data, "description", max_length=300)
            if category_id is None:
                services().rooms.create_category(actor, name=name, description=description)
            else:
                services().rooms.update_category(
                    actor,
                    category_id,
                    version=forms.integer(data, "version"),
                    name=name,
                    description=description,
                )
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("Category saved."), "success")
            return redirect(url_for("rooms.categories"))
    return render_template(
        "rooms/categories.html",
        categories=services().rooms.list_categories(actor),
        errors=errors,
        values=values,
    ), (400 if errors else 200)


# ---------------------------------------------------------------- seasonal rates (5.6)
@bp.route("/rates", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def rates():
    actor = current_actor()
    errors, values = forms.FormErrors(), {}
    if request.method == "POST":
        values = request.form
        try:
            period = services().rooms.add_rate_period(
                actor,
                category_id=forms.integer(values, "category_id"),
                name=forms.text(values, "name", max_length=60),
                first_night=forms.calendar_date(values, "first_night"),
                last_night=forms.calendar_date(values, "last_night"),
                nightly_rate=forms.money(values, "nightly_rate"),
            )
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("Rate period %(name)s added.", name=period.name), "success")
            return redirect(url_for("rooms.rates"))
    return render_template(
        "rooms/rates.html",
        periods=services().rooms.rate_periods(actor),
        categories=services().rooms.list_categories(actor),
        settings=services().hotel_settings.get(actor),
        errors=errors,
        values=values,
    ), (400 if errors else 200)


@bp.post("/rates/<int:period_id>/delete")
@roles_required(Role.MANAGER)
def delete_rate(period_id: int):
    try:
        services().rooms.delete_rate_period(current_actor(), period_id)
    except HotelError as exc:
        flash(message_for(exc.code, exc.params), "danger")
    else:
        flash(_("Rate period removed. Existing bookings keep their prices."), "success")
    return redirect(url_for("rooms.rates"))


# ---------------------------------------------------------------- delete or archive (6.17)
@bp.route("/<int:room_id>/remove", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def remove(room_id: int):
    actor = current_actor()
    room = services().rooms.get_room(actor, room_id).room
    plan = services().rooms.removal_plan(actor, room_id)
    return confirm_removal(
        plan=lambda: plan,
        remove=lambda: services().rooms.remove(actor, room_id),
        title=_("Remove room %(number)s", number=room.number),
        uses_label=_("Stays and maintenance periods: %(count)s", count=plan.uses),
        back_url=url_for("rooms.detail", room_id=room_id),
        list_url=url_for("rooms.index"),
        deleted=_("Room deleted."),
        archived=_("Room archived and out of service. You can find it under Archived."),
    )


@bp.post("/<int:room_id>/restore")
@roles_required(Role.MANAGER)
def restore(room_id: int):
    services().rooms.restore(current_actor(), room_id)
    flash(_("Room restored. It is still out of service: edit it to put it back."), "success")
    return redirect(url_for("rooms.detail", room_id=room_id))

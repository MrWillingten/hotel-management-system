"""The extra-services catalogue, kept by managers (story 4.3)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _

from hotel.domain.enums import Role
from hotel.domain.errors import HotelError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.security import roles_required

bp = Blueprint("extras", __name__, url_prefix="/extras")


@bp.route("/", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def index():
    actor = current_actor()
    errors, values = forms.FormErrors(), {}
    if request.method == "POST":
        values = request.form
        try:
            extra = services().extras.create(
                actor,
                name=forms.text(values, "name", max_length=60),
                unit_price=forms.money(values, "unit_price"),
            )
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("%(name)s added to the catalogue.", name=extra.name), "success")
            return redirect(url_for("extras.index"))
    return render_template(
        "extras/index.html",
        extras=services().extras.catalogue(actor),
        errors=errors,
        values=values,
    ), (400 if errors else 200)


@bp.route("/<int:extra_id>/edit", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def edit(extra_id: int):
    actor = current_actor()
    extra = services().extras.get(actor, extra_id)
    errors, values = forms.FormErrors(), None
    if request.method == "POST":
        values = request.form
        try:
            services().extras.update(
                actor,
                extra_id,
                version=forms.integer(values, "version"),
                name=forms.text(values, "name", max_length=60),
                unit_price=forms.money(values, "unit_price"),
                is_active=forms.checkbox(values, "is_active"),
            )
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("Changes saved."), "success")
            return redirect(url_for("extras.index"))
    return render_template("extras/edit.html", extra=extra, errors=errors, values=values), (
        400 if errors else 200
    )

"""Guest records."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import get_locale
from flask_babel import gettext as _

from hotel.domain.errors import HotelError
from hotel.domain.guests import GuestDetails
from hotel.persistence.repositories.guests import SORT_ORDERS
from hotel.services.guests import ProbableDuplicateError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.messages import message_for
from hotel.web.security import login_required

bp = Blueprint("guests", __name__, url_prefix="/guests")


def _details(data) -> GuestDetails:
    return GuestDetails(
        first_name=forms.text(data, "first_name", max_length=80),
        last_name=forms.text(data, "last_name", max_length=80),
        id_doc_type=forms.text(data, "id_doc_type", max_length=10),
        id_doc_number=forms.text(data, "id_doc_number", max_length=40),
        nationality=forms.text(data, "nationality", max_length=2),
        phone=forms.text(data, "phone", max_length=40),
        email=forms.text(data, "email", max_length=254),
        notes=forms.text(data, "notes", max_length=600),
    )


def country_options() -> list[tuple[str, str]]:
    """Two-letter country codes with their names in the interface language."""
    territories = get_locale().territories
    pairs = [
        (code, name) for code, name in territories.items() if len(code) == 2 and code.isalpha()
    ]
    return sorted(pairs, key=lambda pair: pair[1])


@bp.get("/")
@login_required
def index():
    query = request.args.get("q", "")[:100]
    sort = request.args.get("sort", "name")
    sort = sort if sort in SORT_ORDERS else "name"
    page = services().guests.search(
        current_actor(), query, forms.page_request(request.args), sort=sort
    )
    return render_template("guests/index.html", page=page, query=query, sort=sort)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    errors, duplicates = forms.FormErrors(), []
    if request.method == "POST":
        try:
            guest = services().guests.register(
                current_actor(),
                _details(request.form),
                confirm_duplicate=forms.checkbox(request.form, "confirm_duplicate"),
            )
        except ProbableDuplicateError as exc:
            duplicates = exc.candidates
            errors["__all__"] = message_for(exc.code, exc.params)
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
            if exc.code == "guest.document_taken":
                duplicates = [services().guests.get(current_actor(), exc.params["existing_id"])]
        else:
            flash(_("Guest %(name)s registered.", name=guest.full_name), "success")
            return redirect(url_for("guests.detail", guest_id=guest.id))
    return render_template(
        "guests/form.html",
        guest=None,
        values=request.form,
        errors=errors,
        duplicates=duplicates,
        countries=country_options(),
    ), (400 if errors else 200)


@bp.route("/<int:guest_id>/edit", methods=["GET", "POST"])
@login_required
def edit(guest_id: int):
    guest = services().guests.get(current_actor(), guest_id)
    errors = forms.FormErrors()
    if request.method == "POST":
        try:
            services().guests.update(
                current_actor(),
                guest_id,
                version=forms.integer(request.form, "version"),
                details=_details(request.form),
            )
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("Changes saved."), "success")
            return redirect(url_for("guests.detail", guest_id=guest_id))
    return render_template(
        "guests/form.html",
        guest=guest,
        values=request.form if request.method == "POST" else None,
        errors=errors,
        duplicates=[],
        countries=country_options(),
    ), (400 if errors else 200)


def _detail_page(guest_id: int, *, revealed: str | None = None, errors=None, status: int = 200):
    guest = services().guests.get(current_actor(), guest_id)
    names = dict(country_options())
    return render_template(
        "guests/detail.html",
        guest=guest,
        revealed=revealed,
        country=names.get(guest.nationality or "", guest.nationality),
        errors=errors or forms.FormErrors(),
    ), status


@bp.get("/<int:guest_id>")
@login_required
def detail(guest_id: int):
    return _detail_page(guest_id)


@bp.post("/<int:guest_id>/document")
@login_required
def reveal_document(guest_id: int):
    """Shown in this response only (never stored in a cookie or redirect URL)."""
    number = services().guests.reveal_document(current_actor(), guest_id)
    return _detail_page(guest_id, revealed=number)


@bp.post("/<int:guest_id>/flags")
@login_required
def set_flags(guest_id: int):
    data = request.form
    try:
        services().guests.set_flags(
            current_actor(),
            guest_id,
            version=forms.integer(data, "version"),
            is_vip=forms.checkbox(data, "is_vip"),
            do_not_rent=forms.checkbox(data, "do_not_rent"),
            reason=forms.text(data, "reason", max_length=200),
        )
    except HotelError as exc:
        return _detail_page(guest_id, errors=forms.FormErrors.from_error(exc), status=400)
    flash(_("Changes saved."), "success")
    return redirect(url_for("guests.detail", guest_id=guest_id))

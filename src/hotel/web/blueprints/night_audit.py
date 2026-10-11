"""The night audit page, for managers (story 5.4)."""

from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, render_template, request

from hotel.domain.enums import Role
from hotel.domain.errors import HotelError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.security import roles_required

bp = Blueprint("night_audit", __name__, url_prefix="/night-audit")


def _page(outcome=None, errors=None, status=200):
    actor = current_actor()
    return render_template(
        "night_audit/index.html",
        snapshots=services().night_audit.recent(actor),
        outcome=outcome,
        errors=errors or forms.FormErrors(),
        yesterday=services().clock.today() - timedelta(days=1),
    ), status


@bp.get("/")
@roles_required(Role.MANAGER)
def index():
    return _page()


@bp.post("/")
@roles_required(Role.MANAGER)
def run():
    try:
        outcome = services().night_audit.run(
            current_actor(), forms.calendar_date(request.form, "day")
        )
    except HotelError as exc:
        return _page(errors=forms.FormErrors.from_error(exc), status=400)
    return _page(outcome)

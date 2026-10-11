"""Management statistics, kept for managers (story 5.1, brief §4.8)."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from hotel.domain.enums import Role
from hotel.domain.errors import HotelError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.security import roles_required

bp = Blueprint("reports", __name__, url_prefix="/reports")

DAILY_TABLE_LIMIT = 62  # longer ranges are shown per month


@bp.get("/")
@roles_required(Role.MANAGER)
def index():
    reports = services().reports
    default_first, default_last = reports.default_range()
    args = request.args
    values = {
        "first": args.get("first", default_first.isoformat()),
        "last": args.get("last", default_last.isoformat()),
        "day": args.get("day", services().clock.today().isoformat()),
    }
    report, errors = None, forms.FormErrors()
    try:
        report = reports.report(
            current_actor(),
            forms.calendar_date(values, "first"),
            forms.calendar_date(values, "last"),
            availability_day=forms.calendar_date(values, "day"),
        )
    except HotelError as exc:
        errors = forms.FormErrors.from_error(exc)
    return render_template(
        "reports/index.html",
        report=report,
        values=values,
        errors=errors,
        daily=report is not None and len(report.days) <= DAILY_TABLE_LIMIT,
    ), (400 if errors else 200)

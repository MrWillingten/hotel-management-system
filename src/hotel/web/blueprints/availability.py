"""The availability grid: rooms x the next 14 nights."""

from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, render_template, request

from hotel.domain.errors import ValidationError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.security import login_required

bp = Blueprint("availability", __name__, url_prefix="/availability")
DAYS = 14


@bp.get("/")
@login_required
def index():
    today = services().clock.today()
    try:
        start = forms.calendar_date(request.args, "start", required=False) or today
    except ValidationError:
        start = today
    calendar = services().reservations.calendar(current_actor(), start, days=DAYS)
    return render_template(
        "availability/index.html",
        calendar=calendar,
        previous=start - timedelta(days=7),
        following=start + timedelta(days=7),
        timedelta=timedelta,
    )

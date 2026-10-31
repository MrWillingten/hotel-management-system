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
    actor = current_actor()
    calendar = services().reservations.calendar(actor, start, days=DAYS)
    categories = services().rooms.list_categories(actor)
    # Story 7.4: show one category only; an unknown or empty value shows every room.
    category = request.args.get("category", type=int)
    if category not in {c.id for c in categories}:
        category = None
    rows = [r for r in calendar.rows if category is None or r.room.category_id == category]
    return render_template(
        "availability/index.html",
        calendar=calendar,
        rows=rows,
        categories=categories,
        category=category,
        previous=start - timedelta(days=7),
        following=start + timedelta(days=7),
        timedelta=timedelta,
    )

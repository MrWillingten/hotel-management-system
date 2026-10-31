"""The first screen after signing in: the front desk's day (story 4.1)."""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_babel import lazy_gettext as _l

from hotel.web.context import current_actor, services
from hotel.web.security import login_required
from hotel.web.tour import CHECKLIST_TEXT

bp = Blueprint("dashboard", __name__)


def _greeting(hour: int) -> str:
    if 5 <= hour < 12:
        return str(_l("Good morning"))
    if 12 <= hour < 18:
        return str(_l("Good afternoon"))
    return str(_l("Good evening"))


@bp.get("/")
@login_required
def index():
    svc = services()
    actor = current_actor()
    now = svc.clock.local_now()
    day = svc.front_desk.day(actor)
    return render_template(
        "dashboard/index.html",
        greeting=_greeting(now.hour),
        now=now,
        day=day,
        attention=svc.attention.items(actor, day),
        schema_version=svc.schema_version,
        onboarding=svc.onboarding.state(actor),
        checklist_text=CHECKLIST_TEXT,
    )

"""The first screen after signing in."""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_babel import lazy_gettext as _l

from hotel import __version__
from hotel.web.context import services
from hotel.web.security import login_required

bp = Blueprint("dashboard", __name__)

# Shown on the dashboard until the real front-desk figures arrive in Sprint 4.
ROADMAP = (
    (1, _l("Foundations: sign-in, themes, languages"), "done"),
    (2, _l("Rooms, guests, staff and audit log"), "next"),
    (3, _l("Reservations and availability"), "planned"),
    (4, _l("Front desk and billing"), "planned"),
    (5, _l("Reports, operations and translations"), "planned"),
    (6, _l("Hardening, report and demo"), "planned"),
)


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
    now = svc.clock.local_now()
    return render_template(
        "dashboard/index.html",
        greeting=_greeting(now.hour),
        now=now,
        roadmap=ROADMAP,
        app_version=__version__,
        schema_version=svc.schema_version,
        idle_minutes=svc.auth.session_idle_minutes,
    )

"""The walk-through for new accounts (story 6.14): tour pages and checklist actions."""

from __future__ import annotations

from flask import Blueprint, abort, g, redirect, render_template, url_for

from hotel.web.context import current_actor, services
from hotel.web.security import login_required
from hotel.web.tour import steps_for

bp = Blueprint("welcome", __name__, url_prefix="/welcome")


@bp.get("/<int:step>")
@login_required
def tour(step: int):
    steps = steps_for(g.user.is_manager)
    if not 1 <= step <= len(steps):
        abort(404)
    return render_template("welcome/step.html", step=steps[step - 1], number=step, total=len(steps))


@bp.post("/done")
@login_required
def done():
    """Finish or skip the tour: the welcome card leaves the dashboard."""
    services().onboarding.finish_tour(current_actor())
    return redirect(url_for("dashboard.index"))


@bp.post("/checklist/dismiss")
@login_required
def dismiss_checklist():
    services().onboarding.dismiss_checklist(current_actor())
    return redirect(url_for("dashboard.index"))


@bp.post("/restart")
@login_required
def restart():
    services().onboarding.restart(current_actor())
    return redirect(url_for("welcome.tour", step=1))

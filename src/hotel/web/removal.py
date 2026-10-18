"""The "Remove" confirmation shared by guests, rooms, services, taxes and staff (story 6.17).

Every kind of record follows the same steps: the page explains what will
happen (deleted for good, archived, or not possible now) and why; the
manager ticks a confirmation box; the service decides again inside its
transaction and does it. Only the wording and the URLs differ.
"""

from __future__ import annotations

from collections.abc import Callable

from flask import flash, redirect, render_template, request
from flask_babel import gettext as _

from hotel.domain.errors import HotelError
from hotel.domain.removal import RemovalAction, RemovalPlan
from hotel.web import forms
from hotel.web.messages import message_for


def confirm_removal(
    *,
    plan: Callable[[], RemovalPlan],
    remove: Callable[[], RemovalAction],
    title: str,
    uses_label: str,
    back_url: str,
    list_url: str,
    deleted: str,
    archived: str,
):
    """GET shows the plan; POST (with the box ticked) carries it out."""
    if request.method == "POST":
        if not forms.checkbox(request.form, "confirm"):
            flash(_("Tick the box to confirm."), "warning")
            return redirect(request.path)
        try:
            action = remove()
        except HotelError as exc:
            flash(message_for(exc.code, exc.params), "danger")
            return redirect(back_url)
        flash(deleted if action is RemovalAction.DELETE else archived, "success")
        return redirect(list_url)
    current = plan()
    return render_template(
        "removal/confirm.html",
        plan=current,
        problem=None if current.allowed else message_for(current.blocked, current.params),
        title=title,
        uses_label=uses_label,
        back_url=back_url,
    )

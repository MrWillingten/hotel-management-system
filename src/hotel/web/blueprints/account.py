"""The signed-in user's own account."""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from flask_babel import gettext as _

from hotel.domain.errors import ValidationError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.security import AUTH_COOKIE, login_required

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    errors = forms.FormErrors()
    if request.method == "POST":
        data = request.form
        current = data.get("current_password", "")[:256]
        new = data.get("password", "")[:256]
        if new != data.get("confirm", "")[:256]:
            errors["confirm"] = _("The two passwords are different.")
        else:
            try:
                services().users.change_own_password(
                    current_actor(),
                    current_password=current,
                    new_password=new,
                    current_token=request.cookies.get(AUTH_COOKIE),
                )
            except ValidationError as exc:
                errors = forms.FormErrors.from_error(exc)
            else:
                flash(_("Your password has been changed."), "success")
                return redirect(url_for("dashboard.index"))
    return render_template(
        "account/password.html", errors=errors, forced=g.user.must_change_password
    ), (400 if errors else 200)

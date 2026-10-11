"""Staff accounts (managers only)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _

from hotel.domain.enums import Role
from hotel.domain.errors import BusinessRuleViolation, ConflictError, ValidationError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.messages import message_for
from hotel.web.security import roles_required

bp = Blueprint("staff", __name__, url_prefix="/staff")


def _role(data) -> Role:
    try:
        return Role(data.get("role", ""))
    except ValueError:
        raise ValidationError("user.role_invalid", fields={"role": "user.role_invalid"}) from None


def _temporary_password(data) -> str:
    password = data.get("password", "")[:256]
    if password != data.get("confirm", "")[:256]:
        raise ValidationError("password.mismatch", fields={"confirm": "password.mismatch"})
    return password


@bp.get("/")
@roles_required(Role.MANAGER)
def index():
    users = services().users.list_users(current_actor())
    return render_template("staff/index.html", users=users, now=services().clock.now())


@bp.route("/new", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def create():
    errors, values = forms.FormErrors(), {}
    if request.method == "POST":
        data = request.form
        values = {k: forms.text(data, k, max_length=100) for k in ("username", "full_name", "role")}
        try:
            user = services().users.create_user(
                current_actor(),
                username=values["username"],
                full_name=values["full_name"],
                role=_role(data),
                temporary_password=_temporary_password(data),
            )
        except (ValidationError, ConflictError) as exc:
            errors = _errors(exc)
        else:
            flash(
                _(
                    "Account %(username)s created. Give them the temporary password in person.",
                    username=user.username,
                ),
                "success",
            )
            return redirect(url_for("staff.index"))
    return render_template("staff/new.html", errors=errors, values=values), (400 if errors else 200)


@bp.route("/<int:user_id>", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def edit(user_id: int):
    users = services().users
    errors = forms.FormErrors()
    if request.method == "POST":
        data = request.form
        try:
            users.update_user(
                current_actor(),
                user_id,
                version=forms.integer(data, "version"),
                full_name=forms.text(data, "full_name", max_length=100),
                role=_role(data),
            )
        except (ValidationError, BusinessRuleViolation, ConflictError) as exc:
            errors = _errors(exc)
        else:
            flash(_("Changes saved."), "success")
            return redirect(url_for("staff.edit", user_id=user_id))
    user = users.get_user(current_actor(), user_id)
    return render_template(
        "staff/edit.html", user=user, errors=errors, now=services().clock.now()
    ), (400 if errors else 200)


@bp.post("/<int:user_id>/active")
@roles_required(Role.MANAGER)
def set_active(user_id: int):
    active = forms.checkbox(request.form, "active")
    try:
        services().users.set_active(
            current_actor(), user_id, version=forms.integer(request.form, "version"), active=active
        )
    except (BusinessRuleViolation, ConflictError) as exc:
        flash(message_for(exc.code, exc.params), "danger")
    else:
        flash(
            _("Account reactivated.") if active else _("Account deactivated and signed out."),
            "success",
        )
    return redirect(url_for("staff.edit", user_id=user_id))


@bp.post("/<int:user_id>/password")
@roles_required(Role.MANAGER)
def reset_password(user_id: int):
    try:
        services().users.reset_password(
            current_actor(), user_id, temporary_password=_temporary_password(request.form)
        )
    except ValidationError as exc:
        flash(message_for(exc.code, exc.params), "danger")
    else:
        flash(
            _("Temporary password set. They must choose a new one at their next sign-in."),
            "success",
        )
    return redirect(url_for("staff.edit", user_id=user_id))


@bp.post("/<int:user_id>/unlock")
@roles_required(Role.MANAGER)
def unlock(user_id: int):
    services().users.unlock(current_actor(), user_id)
    flash(_("Account unlocked."), "success")
    return redirect(url_for("staff.edit", user_id=user_id))


def _errors(exc) -> forms.FormErrors:
    return forms.FormErrors.from_error(exc)

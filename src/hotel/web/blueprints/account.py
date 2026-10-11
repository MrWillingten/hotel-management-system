"""The signed-in user's own account."""

from __future__ import annotations

import segno
from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from flask_babel import gettext as _
from markupsafe import Markup

from hotel.domain.api_tokens import LIFETIMES
from hotel.domain.enums import Role
from hotel.domain.errors import BusinessRuleViolation, ValidationError
from hotel.web import forms
from hotel.web.context import cookie_name, current_actor, services, settings
from hotel.web.messages import message_for
from hotel.web.security import AUTH_COOKIE, login_required, roles_required

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
                    current_token=request.cookies.get(cookie_name(AUTH_COOKIE)),
                )
            except ValidationError as exc:
                errors = forms.FormErrors.from_error(exc)
            else:
                flash(_("Your password has been changed."), "success")
                return redirect(url_for("dashboard.index"))
    return render_template(
        "account/password.html", errors=errors, forced=g.user.must_change_password
    ), (400 if errors else 200)


# ---------------------------------------------------------------- two-factor sign-in
def _qr_svg(uri: str) -> Markup:
    """The QR code as inline SVG, drawn on the server (no JavaScript, no image request).

    segno writes only geometry and colour attributes, which the CSP allows;
    the light background keeps the code scannable in the dark theme.
    """
    code = segno.make(uri, error="m")
    svg = code.svg_inline(dark="#000", light="#fff", omitsize=True, svgclass="qr__image")
    # Safe to mark as HTML: segno draws our own otpauth URI, nothing typed by a user.
    return Markup(svg)  # noqa: S704  # nosec B704


def _two_factor_page(errors=None, status_code: int = 200):
    actor = current_actor()
    two_factor = services().two_factor
    status = two_factor.status(actor)
    enrolment = qr = None
    if not status.enabled:
        enrolment = two_factor.begin(actor, issuer=settings().hotel_name)
        qr = _qr_svg(enrolment.uri)
    blocked = g.user.must_enrol_two_factor(services().clock.now())
    return render_template(
        "account/two_factor.html",
        status=status,
        enrolment=enrolment,
        qr_svg=qr,
        blocked=blocked,
        errors=errors or forms.FormErrors(),
    ), status_code


@bp.get("/two-factor")
@login_required
def two_factor():
    return _two_factor_page()


@bp.post("/two-factor/confirm")
@login_required
def confirm_two_factor():
    try:
        codes = services().two_factor.confirm(current_actor(), request.form.get("code", "")[:20])
    except ValidationError as exc:
        return _two_factor_page(forms.FormErrors.from_error(exc), 400)
    except BusinessRuleViolation:
        return redirect(url_for("account.two_factor"))
    flash(_("Two-factor sign-in is on."), "success")
    return render_template("account/recovery_codes.html", codes=codes)


@bp.post("/two-factor/recovery-codes")
@login_required
def renew_recovery_codes():
    try:
        codes = services().two_factor.regenerate_codes(
            current_actor(), request.form.get("code", "")[:20]
        )
    except ValidationError as exc:
        return _two_factor_page(forms.FormErrors.from_error(exc), 400)
    except BusinessRuleViolation as exc:
        flash(message_for(exc.code), "danger")
        return redirect(url_for("account.two_factor"))
    return render_template("account/recovery_codes.html", codes=codes)


@bp.post("/two-factor/disable")
@login_required
def disable_two_factor():
    try:
        services().two_factor.disable(current_actor(), request.form.get("code", "")[:20])
    except (ValidationError, BusinessRuleViolation) as exc:
        flash(message_for(exc.code), "danger")
    else:
        flash(_("Two-factor sign-in is off."), "info")
    return redirect(url_for("account.two_factor"))


# ---------------------------------------------------------------- API tokens (story 6.3)
def _api_tokens_page(errors=None, created=None, status_code: int = 200):
    return render_template(
        "account/api_tokens.html",
        tokens=services().api_tokens.list_own(current_actor()),
        lifetimes=[(str(days), _("Days: %(n)s", n=days)) for days in LIFETIMES],
        created=created,
        now=services().clock.now(),
        errors=errors or forms.FormErrors(),
    ), status_code


@bp.get("/api-tokens")
@roles_required(Role.MANAGER)
def api_tokens():
    return _api_tokens_page()


@bp.post("/api-tokens")
@roles_required(Role.MANAGER)
def create_api_token():
    days = request.form.get("days", "")
    try:
        created = services().api_tokens.create(
            current_actor(),
            name=request.form.get("name", "")[:100],
            days=int(days) if days.isdigit() else 0,
        )
    except ValidationError as exc:
        return _api_tokens_page(forms.FormErrors.from_error(exc), status_code=400)
    except BusinessRuleViolation as exc:
        flash(message_for(exc.code, exc.params), "danger")
        return redirect(url_for("account.api_tokens"))
    # Shown in this response only: the database keeps nothing it could be read back from.
    return _api_tokens_page(created=created)


@bp.post("/api-tokens/<int:token_id>/revoke")
@roles_required(Role.MANAGER)
def revoke_api_token(token_id: int):
    services().api_tokens.revoke(current_actor(), token_id)
    flash(_("The token was revoked. Programs using it can no longer read data."), "info")
    return redirect(url_for("account.api_tokens"))

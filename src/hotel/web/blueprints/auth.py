"""Sign in and sign out."""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from flask_babel import gettext as _

from hotel.domain.errors import AuthenticationError
from hotel.web.context import services, settings
from hotel.web.messages import message_for
from hotel.web.security import AUTH_COOKIE, is_safe_redirect_target, public

bp = Blueprint("auth", __name__)


def _next_target() -> str | None:
    target = request.values.get("next")
    return target if is_safe_redirect_target(target) else None


@bp.route("/login", methods=["GET", "POST"])
@public
def login():
    auth = services().auth
    next_target = _next_target()
    if g.user is not None and request.method == "GET":
        return redirect(next_target or url_for("dashboard.index"))

    error = None
    username = ""
    status = 200
    if request.method == "POST":
        username = request.form.get("username", "")[:64]
        password = request.form.get("password", "")[:256]
        try:
            result = auth.login(
                username,
                password,
                ip=request.remote_addr or "unknown",
                user_agent=request.user_agent.string,
            )
        except AuthenticationError as exc:
            error = message_for(exc.code, exc.params)
            status = 401
        else:
            if result.needs_code:
                # Second step: the challenge rides in Flask's signed cookie; it is
                # useless without the code, and the server forgets it in 5 minutes.
                session["login_challenge"] = result.challenge
                session["login_next"] = next_target
                return redirect(url_for("auth.verify"))
            return _signed_in(result, next_target)

    return (
        render_template(
            "auth/login.html",
            error=error,
            username=username,
            next=next_target,
            needs_setup=not auth.has_users(),
        ),
        status,
    )


@bp.route("/login/code", methods=["GET", "POST"])
@public
def verify():
    """The six digits from the authenticator app, or a recovery code (story 6.1)."""
    challenge = session.get("login_challenge")
    if not challenge:
        return redirect(url_for("auth.login"))
    error = None
    status = 200
    if request.method == "POST":
        try:
            result = services().auth.complete_login(
                challenge,
                request.form.get("code", ""),
                ip=request.remote_addr or "unknown",
                user_agent=request.user_agent.string,
            )
        except AuthenticationError as exc:
            if exc.code != "auth.invalid_code":
                session.pop("login_challenge", None)
                flash(message_for(exc.code, exc.params), "danger")
                return redirect(url_for("auth.login"))
            error = message_for(exc.code, exc.params)
            status = 401
        else:
            return _signed_in(result, session.get("login_next"))
    return render_template("auth/verify.html", error=error), status


def _signed_in(result, next_target: str | None = None):
    """Hand the browser its new session cookie."""
    next_target = next_target if is_safe_redirect_target(next_target) else None
    # Never keep a session id from before the login (session fixation):
    # end any previous server session and start a fresh Flask session,
    # which also gives the user a new CSRF token.
    services().auth.logout(request.cookies.get(AUTH_COOKIE))
    session.clear()
    g.clear_auth_cookie = False
    response = redirect(next_target or url_for("dashboard.index"))
    response.set_cookie(
        AUTH_COOKIE,
        result.token,
        httponly=True,
        samesite="Lax",
        secure=settings().https,
        path="/",
    )
    flash(_("Welcome, %(name)s.", name=result.user.full_name), "success")
    return response


@bp.post("/logout")
@public  # must work even when the session has already expired
def logout():
    services().auth.logout(request.cookies.get(AUTH_COOKIE))
    session.clear()
    response = redirect(url_for("auth.login"))
    response.delete_cookie(AUTH_COOKIE, path="/")
    flash(_("You have been signed out."), "info")
    return response

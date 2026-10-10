"""Changing the interface language and colour theme."""

from __future__ import annotations

from flask import Blueprint, abort, redirect, request, url_for

from hotel.config import LANGUAGES
from hotel.web.context import settings
from hotel.web.preferences import LANG_COOKIE, THEME_COOKIE, THEMES, remember
from hotel.web.security import is_safe_redirect_target, public

bp = Blueprint("preferences", __name__, url_prefix="/preferences")


def _back():
    target = request.form.get("next")
    return redirect(target if is_safe_redirect_target(target) else url_for("dashboard.index"))


def _save(cookie: str, allowed: tuple[str, ...], field: str):
    value = request.form.get(field, "")
    if value not in allowed:  # whitelist: nothing else ever reaches a cookie
        abort(400)
    response = _back()
    remember(response, cookie, value, secure=settings().https)
    return response


@bp.post("/theme")
@public
def set_theme():
    return _save(THEME_COOKIE, THEMES, "theme")


@bp.post("/language")
@public
def set_language():
    return _save(LANG_COOKIE, LANGUAGES, "language")

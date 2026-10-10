"""Interface preferences (language and theme), kept in cookies.

The server reads them on every request and renders the page directly in the
right language, direction and colour theme, so there is no flash of the wrong
theme and no JavaScript is needed.
"""

from __future__ import annotations

from flask import Response, request

from hotel.config import LANGUAGES, RTL_LANGUAGES

LANG_COOKIE = "hotel_lang"
THEME_COOKIE = "hotel_theme"
THEMES = ("light", "dark", "system")
_ONE_YEAR = 365 * 24 * 3600


def select_locale() -> str:
    chosen = request.cookies.get(LANG_COOKIE)
    if chosen in LANGUAGES:
        return chosen
    return request.accept_languages.best_match(LANGUAGES) or "en"


def text_direction(locale: str) -> str:
    return "rtl" if locale in RTL_LANGUAGES else "ltr"


def current_theme() -> str:
    chosen = request.cookies.get(THEME_COOKIE)
    return chosen if chosen in THEMES else "system"


def remember(response: Response, cookie: str, value: str, *, secure: bool) -> None:
    response.set_cookie(
        cookie, value, max_age=_ONE_YEAR, httponly=True, samesite="Lax", secure=secure, path="/"
    )

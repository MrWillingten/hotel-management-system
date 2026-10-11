"""The web interface: a Flask application built around the services."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, request, url_for
from flask_babel import Babel, get_locale
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from hotel import __version__
from hotel.bootstrap import Services, build_services
from hotel.config import LANGUAGES, ConfigurationError, Settings
from hotel.demo import is_demo
from hotel.secret_key import load_or_create_secret_key
from hotel.web import errors, security
from hotel.web.blueprints import (
    account,
    audit,
    auth,
    availability,
    backups,
    billing,
    dashboard,
    extras,
    guests,
    hotel_settings,
    invoices,
    preferences,
    reservations,
    rooms,
    staff,
)
from hotel.web.context import SERVICES_KEY
from hotel.web.formatting import money, percent
from hotel.web.preferences import current_theme, select_locale, text_direction

TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "translations"
LANGUAGE_NAMES = {"en": "English", "fr": "Français", "ar": "العربية"}

csrf = CSRFProtect()
babel = Babel()


def _debug_requested() -> bool:
    return os.environ.get("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def create_app(settings: Settings | None = None, *, services: Services | None = None) -> Flask:
    settings = settings or Settings.from_env()
    if settings.environment == "production" and _debug_requested():
        # The Werkzeug debugger lets anyone who can reach it run code on the server.
        raise ConfigurationError("Debug mode is forbidden in production (unset FLASK_DEBUG).")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=load_or_create_secret_key(settings.secret_key_path),
        DEBUG=settings.debug,
        TESTING=settings.environment == "testing",
        MAX_CONTENT_LENGTH=1024 * 1024,
        # Flask's own signed cookie only carries flash messages and the CSRF token;
        # authentication uses the server-side session (see security.AUTH_COOKIE).
        SESSION_COOKIE_NAME="hotel_ui",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.https,
        WTF_CSRF_TIME_LIMIT=8 * 3600,  # one working shift
        BABEL_DEFAULT_LOCALE="en",
        BABEL_DEFAULT_TIMEZONE=settings.timezone,
        BABEL_TRANSLATION_DIRECTORIES=str(TRANSLATIONS_DIR),
    )
    if settings.trusted_proxies:
        n = settings.trusted_proxies
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    _configure_logging(app, settings)
    app.extensions[SERVICES_KEY] = services or build_services(settings)

    csrf.init_app(app)
    babel.init_app(app, locale_selector=select_locale)
    security.install(app)
    errors.install(app)
    for blueprint in (
        account.bp,
        audit.bp,
        auth.bp,
        availability.bp,
        backups.bp,
        billing.bp,
        dashboard.bp,
        extras.bp,
        guests.bp,
        hotel_settings.bp,
        invoices.bp,
        preferences.bp,
        reservations.bp,
        rooms.bp,
        staff.bp,
    ):
        app.register_blueprint(blueprint)

    app.add_template_filter(money, "money")
    app.add_template_filter(percent, "percent")

    @app.template_filter("options")
    def options_filter(items, value: str = "id", label: str = "name") -> list[tuple]:
        """Records -> (value, label) pairs for the select() form macro."""
        return [(getattr(item, value), getattr(item, label)) for item in items]

    @app.template_global()
    def page_url(page: int) -> str:
        """The current URL with a different ?page=, keeping every other filter."""
        args = request.args.to_dict()
        args["page"] = str(page)
        return url_for(request.endpoint, **(request.view_args or {}), **args)

    @app.context_processor
    def interface_context():
        locale = str(get_locale() or "en")
        return {
            "current_user": g.get("user"),
            "demo_mode": is_demo(app.extensions[SERVICES_KEY]),
            "locale": locale,
            "text_dir": text_direction(locale),
            "theme": current_theme(),
            "hotel_name": settings.hotel_name,
            "app_version": __version__,
            "languages": [(code, LANGUAGE_NAMES[code]) for code in LANGUAGES],
        }

    return app


def _configure_logging(app: Flask, settings: Settings) -> None:
    app.logger.setLevel(logging.INFO)
    if settings.environment != "production":
        return
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "hotel.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app.logger.addHandler(handler)

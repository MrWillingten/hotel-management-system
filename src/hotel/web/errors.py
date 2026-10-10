"""Turning failures into friendly pages.

Expected business errors (HotelError) become pages with a translated
explanation. Anything unexpected is logged with its full traceback under a
short incident id, and the user only sees that id: never a traceback, SQL or
file path.
"""

from __future__ import annotations

import secrets

from flask import Flask, render_template
from flask_babel import lazy_gettext as _l
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from hotel.domain.errors import (
    AuthenticationError,
    BusinessRuleViolation,
    ConflictError,
    HotelError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from hotel.web.messages import message_for

_STATUS_FOR = (
    (ValidationError, 400),
    (AuthenticationError, 401),
    (PermissionDeniedError, 403),
    (NotFoundError, 404),
    (ConflictError, 409),
    (BusinessRuleViolation, 409),
)

_HTTP_TEXT = {
    400: (_l("Bad request"), _l("The request couldn't be understood.")),
    403: (_l("Access denied"), _l("You don't have permission to open this page.")),
    404: (_l("Page not found"), _l("The page you asked for doesn't exist.")),
    405: (_l("Not allowed"), _l("This action can't be done this way.")),
    413: (_l("Too large"), _l("The data sent was too large.")),
    500: (_l("Something went wrong"), _l("An unexpected error occurred. It has been logged.")),
}


def _page(status: int, title: str, message: str, incident: str | None = None):
    return (
        render_template(
            "errors/error.html", status=status, title=title, message=message, incident=incident
        ),
        status,
    )


def install(app: Flask) -> None:
    @app.errorhandler(HotelError)
    def handle_hotel_error(error: HotelError):
        status = next((s for cls, s in _STATUS_FOR if isinstance(error, cls)), 400)
        title = _HTTP_TEXT.get(status, _HTTP_TEXT[400])[0]
        return _page(status, str(title), message_for(error.code, error.params))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        return _page(
            400,
            str(_l("Form expired")),
            str(
                _l(
                    "This form expired or was sent from another site. "
                    "Reload the page and try again."
                )
            ),
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        status = error.code or 500
        title, message = _HTTP_TEXT.get(status, (error.name, error.description))
        return _page(status, str(title), str(message))

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        incident = secrets.token_hex(4)
        app.logger.exception("Unhandled error, incident %s", incident)
        title, message = _HTTP_TEXT[500]
        return _page(500, str(title), str(message), incident=incident)

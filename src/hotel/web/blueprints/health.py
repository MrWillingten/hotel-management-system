"""Liveness check for containers and monitoring (story 6.2).

Public on purpose (a health checker has no account) and tells nothing
beyond "up" or "down": no version, no counts, no error text.
"""

from __future__ import annotations

from flask import Blueprint, current_app

from hotel.web.context import services
from hotel.web.security import public

bp = Blueprint("health", __name__)


@bp.get("/health")
@public
def health():
    if services().is_healthy():
        return {"status": "ok"}
    current_app.logger.error("Health check failed: the database cannot be read")
    return {"status": "unavailable"}, 503

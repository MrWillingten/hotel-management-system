"""Access to the application's services from inside a request."""

from __future__ import annotations

from flask import current_app

from hotel.bootstrap import Services
from hotel.config import Settings

SERVICES_KEY = "hotel.services"


def services() -> Services:
    return current_app.extensions[SERVICES_KEY]


def settings() -> Settings:
    return services().settings

"""Access to the application's services from inside a request."""

from __future__ import annotations

from flask import current_app, g, request

from hotel.bootstrap import Services
from hotel.config import Settings
from hotel.domain.actor import Actor

SERVICES_KEY = "hotel.services"


def services() -> Services:
    return current_app.extensions[SERVICES_KEY]


def settings() -> Settings:
    return services().settings


def current_actor() -> Actor:
    """The signed-in user and their address, for role checks and the audit log."""
    return Actor(user=g.get("user"), ip=request.remote_addr, label="anonymous")

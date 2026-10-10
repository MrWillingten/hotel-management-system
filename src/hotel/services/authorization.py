"""Role checks inside services.

Routes already check roles, but a service never trusts that: if a route ever
forgets its check, the service still refuses (defence in depth).
"""

from __future__ import annotations

from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from hotel.domain.errors import PermissionDeniedError


def require_role(actor: Actor, *roles: Role) -> Actor:
    """Allow active users with one of `roles`, and the command line (system actor)."""
    if actor.is_system:
        return actor
    user = actor.user
    if user is None or not user.is_active or user.role not in roles:
        raise PermissionDeniedError(required=",".join(r.value for r in roles))
    return actor


def require_staff(actor: Actor) -> Actor:
    return require_role(actor, Role.RECEPTIONIST, Role.MANAGER)

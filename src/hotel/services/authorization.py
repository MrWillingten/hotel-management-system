"""Role checks inside services.

Routes already check roles, but a service never trusts that: if a route ever
forgets its check, the service still refuses (defence in depth).
"""

from __future__ import annotations

from hotel.domain.enums import Role
from hotel.domain.errors import PermissionDeniedError
from hotel.domain.users import User


def require_role(actor: User | None, *roles: Role) -> User:
    if actor is None or not actor.is_active or actor.role not in roles:
        raise PermissionDeniedError(required=",".join(r.value for r in roles))
    return actor

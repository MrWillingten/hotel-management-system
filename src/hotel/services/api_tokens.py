"""Managers' personal tokens for the read-only JSON API (story 6.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from hotel.domain.actor import Actor
from hotel.domain.api_tokens import (
    MAX_ACTIVE_PER_USER,
    ApiToken,
    new_token,
    validate_lifetime,
    validate_name,
)
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import BusinessRuleViolation, NotFoundError
from hotel.domain.users import User
from hotel.persistence.unit_of_work import UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.auth import hash_token
from hotel.services.authorization import require_role

_MAX_TOKEN_LENGTH = 128
# Like sessions: "last used" is written at most once a minute, not on every call.
_TOUCH_INTERVAL = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class CreatedToken:
    token: ApiToken
    secret: str  # the full token, shown once and never stored


class ApiTokenService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def list_own(self, actor: Actor) -> list[ApiToken]:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return uow.api_tokens.for_user(actor.user.id)

    def create(self, actor: Actor, *, name: str, days: int) -> CreatedToken:
        require_role(actor, Role.MANAGER)
        name = validate_name(name)
        lifetime = validate_lifetime(days)
        now = self._clock.now()
        with self._uow() as uow:
            if uow.api_tokens.count_active(actor.user.id, now) >= MAX_ACTIVE_PER_USER:
                raise BusinessRuleViolation("api_token.too_many", max=MAX_ACTIVE_PER_USER)
            secret = new_token()
            token = uow.api_tokens.add(
                ApiToken(
                    id=None,
                    user_id=actor.user.id,
                    name=name,
                    token_hash=hash_token(secret),
                    prefix=secret[:10],
                    created_at=now,
                    expires_at=now + lifetime,
                )
            )
            record(
                uow,
                self._clock,
                actor,
                "api_token.created",
                entity="api_token",
                entity_id=token.id,
                name=name,
                days=days,
            )
            return CreatedToken(token, secret)

    def revoke(self, actor: Actor, token_id: int) -> None:
        """Managers revoke their own tokens; deactivating an account stops all of its tokens."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            token = uow.api_tokens.get(token_id)
            if token is None or token.user_id != actor.user.id:
                raise NotFoundError(entity="api_token", id=token_id)
            if token.revoked_at is not None:
                return
            uow.api_tokens.revoke(token_id, self._clock.now())
            record(
                uow, self._clock, actor, "api_token.revoked", entity="api_token", entity_id=token_id
            )

    def authenticate(self, secret: str | None) -> User | None:
        """The manager a presented token belongs to, or None.

        A token stops working when it expires or is revoked, and also when its
        owner is deactivated or is no longer a manager.
        """
        if not secret or len(secret) > _MAX_TOKEN_LENGTH:
            return None
        now = self._clock.now()
        with self._uow() as uow:
            token = uow.api_tokens.get_by_hash(hash_token(secret))
            if token is None or not token.is_valid(now):
                return None
            user = uow.users.get(token.user_id)
            if user is None or not user.is_active or not user.is_manager:
                return None
            if token.last_used_at is None or now - token.last_used_at >= _TOUCH_INTERVAL:
                uow.api_tokens.touch(token.id, now)
            return user

"""One-time form tokens.

A double click on "Confirm booking" sends the same form twice. Each form that
must never run twice carries a random token; the first submission uses it up,
so the second one is refused instead of creating a second booking.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.persistence.unit_of_work import UnitOfWorkFactory
from hotel.services.auth import hash_token

TOKEN_LIFETIME = timedelta(hours=8)


class FormTokenService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def issue(self, actor: Actor) -> str:
        if actor.user_id is None:
            return ""
        token = secrets.token_urlsafe(24)
        now = self._clock.now()
        with self._uow() as uow:
            uow.form_tokens.delete_older_than(now - TOKEN_LIFETIME)
            uow.form_tokens.add(hash_token(token), actor.user_id, now)
        return token

    def consume(self, actor: Actor, token: str | None) -> bool:
        if not token or actor.user_id is None or len(token) > 100:
            return False
        with self._uow() as uow:
            return uow.form_tokens.consume(
                hash_token(token), actor.user_id, self._clock.now() - TOKEN_LIFETIME
            )

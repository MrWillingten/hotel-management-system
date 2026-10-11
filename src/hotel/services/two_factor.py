"""Setting up and managing the second sign-in factor (story 6.1).

Enrolment happens in two steps so nobody can lock themselves out: the page
shows a new secret (QR code), and the secret is switched on only after the
user typed a correct code from their phone. Recovery codes are then shown
once; only their hashes are kept.

Managers must enrol (after a 7-day grace period); receptionists may.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import (
    BusinessRuleViolation,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from hotel.domain.totp import (
    grouped,
    hash_recovery_code,
    new_recovery_codes,
    provisioning_uri,
)
from hotel.domain.users import User
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role


@dataclass(frozen=True, slots=True)
class TwoFactorStatus:
    enabled: bool
    enabled_at: datetime | None
    recovery_codes_left: int
    required: bool  # managers
    grace_until: datetime | None


@dataclass(frozen=True, slots=True)
class Enrolment:
    secret: str  # for typing by hand, shown grouped
    uri: str  # what the QR code contains

    @property
    def grouped_secret(self) -> str:
        return grouped(self.secret)


class TwoFactorService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def status(self, actor: Actor) -> TwoFactorStatus:
        with self._uow() as uow:
            user = self._own(uow, actor)
            return TwoFactorStatus(
                enabled=user.two_factor.enabled,
                enabled_at=user.two_factor.enabled_at,
                recovery_codes_left=uow.recovery_codes.remaining(user.id),
                required=user.is_manager,
                grace_until=user.two_factor.grace_until,
            )

    def begin(self, actor: Actor, *, issuer: str) -> Enrolment:
        """The secret to scan; the same one until it is confirmed (reloading the page is safe)."""
        with self._uow() as uow:
            user = self._own(uow, actor)
            if user.two_factor.enabled:
                raise BusinessRuleViolation("totp.already_enabled")
            had_secret = user.two_factor.pending_secret is not None
            secret = user.two_factor.begin_enrolment()
            if not had_secret:
                uow.users.update(user)
            return Enrolment(secret, provisioning_uri(secret, account=user.username, issuer=issuer))

    def confirm(self, actor: Actor, code: str) -> list[str]:
        """Switch the second factor on; returns the recovery codes to show once."""
        now = self._clock.now()
        with self._uow() as uow:
            user = self._own(uow, actor)
            if user.two_factor.enabled:
                raise BusinessRuleViolation("totp.already_enabled")
            user.two_factor.confirm_enrolment(code, now)
            uow.users.update(user)
            codes = self._new_codes(uow, user)
            record(uow, self._clock, actor, "totp.enabled", entity="user", entity_id=user.id)
            return codes

    def regenerate_codes(self, actor: Actor, code: str) -> list[str]:
        """New recovery codes (the old ones stop working); needs a current code."""
        now = self._clock.now()
        with self._uow() as uow:
            user = self._own(uow, actor)
            self._require_code(user, code, now)
            uow.users.update(user)
            codes = self._new_codes(uow, user)
            record(
                uow,
                self._clock,
                actor,
                "totp.recovery_codes_renewed",
                entity="user",
                entity_id=user.id,
            )
            return codes

    def disable(self, actor: Actor, code: str) -> None:
        """Receptionists may turn it off again; managers may not (it is required)."""
        now = self._clock.now()
        with self._uow() as uow:
            user = self._own(uow, actor)
            if user.is_manager:
                raise BusinessRuleViolation("totp.required_for_managers")
            self._require_code(user, code, now)
            user.two_factor.reset(now)
            uow.users.update(user)
            uow.recovery_codes.delete_for_user(user.id)
            record(uow, self._clock, actor, "totp.disabled", entity="user", entity_id=user.id)

    def reset(self, actor: Actor, user_id: int) -> User:
        """Forget a lost phone (`hotel reset-totp`): codes and sessions go too.

        A manager must set up the new phone at the next sign-in.
        """
        require_role(actor, Role.MANAGER)
        now = self._clock.now()
        with self._uow() as uow:
            user = uow.users.get(user_id)
            if user is None:
                raise NotFoundError(entity="user", id=user_id)
            user.two_factor.reset(now)
            uow.users.update(user)
            uow.recovery_codes.delete_for_user(user.id)
            uow.sessions.delete_for_user(user.id)
            record(uow, self._clock, actor, "totp.reset", entity="user", entity_id=user.id)
            return user

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _own(uow: UnitOfWork, actor: Actor) -> User:
        if actor.user is None:
            raise PermissionDeniedError
        user = uow.users.get(actor.user.id)
        if user is None:
            raise NotFoundError(entity="user", id=actor.user.id)
        return user

    @staticmethod
    def _require_code(user: User, code: str, now: datetime) -> None:
        if not user.two_factor.enabled:
            raise BusinessRuleViolation("totp.not_enabled")
        if not user.two_factor.accept(code, now):
            raise ValidationError("totp.wrong_code", fields={"code": "totp.wrong_code"})

    @staticmethod
    def _new_codes(uow: UnitOfWork, user: User) -> list[str]:
        codes = new_recovery_codes()
        uow.recovery_codes.replace(user.id, [hash_recovery_code(c) for c in codes])
        return codes

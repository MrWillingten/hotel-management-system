"""The extra-services catalogue and the charges made to stays (story 4.3)."""

from __future__ import annotations

from datetime import date

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.extras import (
    Extra,
    ServiceCharge,
    validate_charge,
    validate_extra_name,
    validate_unit_price,
    validate_void_reason,
)
from hotel.domain.money import Money
from hotel.domain.removal import RemovalAction, RemovalPlan, plan_removal
from hotel.domain.reservations import ReservationStatus
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role, require_staff


class ExtrasService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    # ------------------------------------------------------------ catalogue
    def catalogue(
        self, actor: Actor, *, active_only: bool = False, archived: bool = False
    ) -> list[Extra]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.extras.list(active_only=active_only, archived=archived)

    # ------------------------------------------------------------ delete or archive (6.17)
    def count_archived(self, actor: Actor) -> int:
        require_staff(actor)
        with self._uow() as uow:
            return uow.extras.count_archived()

    def removal_plan(self, actor: Actor, extra_id: int) -> RemovalPlan:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            self._load(uow, extra_id)
            return plan_removal(uow.extras.count_charges(extra_id))

    def remove(self, actor: Actor, extra_id: int) -> RemovalAction:
        """Delete a service never charged; archive one that was (its charges keep it)."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            extra = self._load(uow, extra_id)
            plan = plan_removal(uow.extras.count_charges(extra_id))
            if plan.action is RemovalAction.DELETE:
                uow.extras.delete(extra_id)
            elif not extra.is_archived:
                uow.extras.archive(extra_id, self._clock.now())
            action = "extra.deleted" if plan.action is RemovalAction.DELETE else "extra.archived"
            record(
                uow, self._clock, actor, action, entity="extra", entity_id=extra_id, name=extra.name
            )
            return plan.action

    def restore(self, actor: Actor, extra_id: int) -> Extra:
        """Back in the catalogue, still inactive until a manager activates it."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            extra = self._load(uow, extra_id)
            if extra.is_archived:
                uow.extras.archive(extra_id, None)
                record(
                    uow, self._clock, actor, "extra.restored", entity="extra", entity_id=extra_id
                )
            return uow.extras.get(extra_id)

    @staticmethod
    def _load(uow: UnitOfWork, extra_id: int) -> Extra:
        extra = uow.extras.get(extra_id)
        if extra is None:
            raise NotFoundError(entity="extra", id=extra_id)
        return extra

    def get(self, actor: Actor, extra_id: int) -> Extra:
        require_staff(actor)
        with self._uow() as uow:
            extra = uow.extras.get(extra_id)
        if extra is None:
            raise NotFoundError(entity="extra", id=extra_id)
        return extra

    def create(self, actor: Actor, *, name: str, unit_price: Money) -> Extra:
        require_role(actor, Role.MANAGER)
        extra = Extra(None, validate_extra_name(name), validate_unit_price(unit_price))
        with self._uow() as uow:
            if uow.extras.name_taken(extra.name):
                raise ConflictError("extra.name_taken", fields={"name": "extra.name_taken"})
            extra = uow.extras.add(extra)
            record(
                uow,
                self._clock,
                actor,
                "extra.created",
                entity="extra",
                entity_id=extra.id,
                name=extra.name,
                price=str(extra.unit_price),
            )
            return extra

    def update(
        self,
        actor: Actor,
        extra_id: int,
        *,
        version: int,
        name: str,
        unit_price: Money,
        is_active: bool,
    ) -> Extra:
        """A new price applies to future charges only (BR20)."""
        require_role(actor, Role.MANAGER)
        name, unit_price = validate_extra_name(name), validate_unit_price(unit_price)
        with self._uow() as uow:
            extra = uow.extras.get(extra_id)
            if extra is None:
                raise NotFoundError(entity="extra", id=extra_id)
            if extra.version != version:
                raise StaleDataError(entity="extra", id=extra_id)
            if extra.is_archived:
                raise BusinessRuleViolation("extra.archived")
            if uow.extras.name_taken(name, except_id=extra_id):
                raise ConflictError("extra.name_taken", fields={"name": "extra.name_taken"})
            before = str(extra.unit_price)
            extra.name, extra.unit_price, extra.is_active = name, unit_price, is_active
            uow.extras.update(extra)
            record(
                uow,
                self._clock,
                actor,
                "extra.updated",
                entity="extra",
                entity_id=extra.id,
                price_before=before,
                price_after=str(unit_price),
                active=is_active,
            )
            return extra

    # ------------------------------------------------------------ charges
    def charges_for(self, actor: Actor, reservation_id: int) -> list[ServiceCharge]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.charges.for_reservation(reservation_id)

    def charge(
        self,
        actor: Actor,
        reservation_id: int,
        *,
        extra_id: int,
        quantity: int,
        charge_date: date | None = None,
    ) -> ServiceCharge:
        """Scenario §4.6: add breakfasts, an airport transfer... to a guest's bill."""
        require_staff(actor)
        today = self._clock.today()
        charge_date = charge_date or today
        with self._uow() as uow:
            reservation = uow.reservations.get(reservation_id)
            if reservation is None:
                raise NotFoundError(entity="reservation", id=reservation_id)
            validate_charge(reservation, charge_date, quantity, today)
            extra = uow.extras.get(extra_id)
            if extra is None or not extra.is_active:
                raise ValidationError("extra.unknown", fields={"extra_id": "extra.unknown"})
            charge = uow.charges.add(
                ServiceCharge(
                    id=None,
                    reservation_id=reservation_id,
                    extra_id=extra.id,
                    description=extra.name,
                    quantity=quantity,
                    unit_price=extra.unit_price,
                    charge_date=charge_date,
                    created_by=actor.user_id,
                    created_at=self._clock.now(),
                )
            )
            record(
                uow,
                self._clock,
                actor,
                "charge.added",
                entity="reservation",
                entity_id=reservation_id,
                charge_id=charge.id,
                extra=extra.name,
                quantity=quantity,
                amount=str(charge.amount),
            )
            return charge

    def void(self, actor: Actor, charge_id: int, *, reason: str) -> ServiceCharge:
        """Correct a wrong charge. Managers only, with a reason; the line stays visible."""
        require_role(actor, Role.MANAGER)
        reason = validate_void_reason(reason)
        with self._uow() as uow:
            charge = uow.charges.get(charge_id)
            if charge is None:
                raise NotFoundError(entity="service_charge", id=charge_id)
            reservation = uow.reservations.get(charge.reservation_id)
            # After check-out the invoice is issued and immutable (BR22).
            if reservation.status is not ReservationStatus.CHECKED_IN:
                raise BusinessRuleViolation("charge.bill_closed")
            if charge.is_void:
                raise BusinessRuleViolation("charge.already_void")
            charge.voided_at = self._clock.now()
            charge.voided_by = actor.user_id
            charge.void_reason = reason
            uow.charges.void(charge)
            record(
                uow,
                self._clock,
                actor,
                "charge.voided",
                entity="reservation",
                entity_id=charge.reservation_id,
                charge_id=charge.id,
                amount=str(charge.amount),
            )
            return charge

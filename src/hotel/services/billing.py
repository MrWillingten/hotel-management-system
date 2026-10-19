"""Bills, discounts, payments and refunds (stories 4.4, 4.5, 4.6)."""

from __future__ import annotations

from hotel.domain.actor import Actor
from hotel.domain.billing import (
    Bill,
    Discount,
    Payment,
    PaymentKind,
    PaymentMethod,
    build_bill,
    check_discount_cap,
    check_payment,
    payment_kind_for,
    validate_reference,
)
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import BusinessRuleViolation, NotFoundError
from hotel.domain.money import Money
from hotel.domain.reservations import Reservation, ReservationStatus
from hotel.domain.taxes import TaxExemption, TaxRule, is_national, taxes_for_stay
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role, require_staff
from hotel.services.hotel_settings import load_settings

# A discount changes the price, so it is only possible while the bill is open.
_OPEN_BILL = (ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN)


def applicable_taxes(uow: UnitOfWork, reservation: Reservation) -> list[TaxRule]:
    """The taxes this stay pays (story 6.16): by the guest's nationality, minus exemptions."""
    settings = load_settings(uow)
    guest = uow.guests.get(reservation.guest_id)
    national = is_national(guest.nationality, guest.id_doc_type, settings.home_country)
    exempt = {e.tax_rule_id for e in uow.tax_exemptions.for_reservation(reservation.id)}
    return taxes_for_stay(
        uow.tax_rules.list(active_only=True), national=national, exempt_rule_ids=exempt
    )


def bill_for(uow: UnitOfWork, reservation: Reservation) -> Bill:
    """Everything stored for this reservation, priced by the domain (build_bill)."""
    return build_bill(
        reservation,
        charges=uow.charges.for_reservation(reservation.id),
        discounts=uow.discounts.for_reservation(reservation.id),
        taxes=applicable_taxes(uow, reservation),
        payments=uow.payments.for_reservation(reservation.id),
        discount_cap_bp=load_settings(uow).discount_cap_bp,
    )


class BillingService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    # ------------------------------------------------------------ reading
    def bill(self, actor: Actor, reservation_id: int) -> Bill:
        """Story 4.4: the bill as it stands now (a preview until check-out)."""
        require_staff(actor)
        with self._uow() as uow:
            return bill_for(uow, self._load(uow, reservation_id))

    def discounts(self, actor: Actor, reservation_id: int) -> list[Discount]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.discounts.for_reservation(reservation_id)

    # ------------------------------------------------------------ discounts
    def grant_discount(self, actor: Actor, discount: Discount) -> Discount:
        """Decision Q3 / threat A6: managers only, reason required, capped."""
        require_role(actor, Role.MANAGER)
        discount.validate()
        with self._uow() as uow:
            reservation = self._load(uow, discount.reservation_id)
            if reservation.status not in _OPEN_BILL:
                raise BusinessRuleViolation("discount.bill_closed")
            check_discount_cap(
                uow.discounts.for_reservation(reservation.id),
                discount,
                reservation.accommodation_total,
                load_settings(uow).discount_cap_bp,
            )
            discount.approved_by = actor.user_id
            discount.created_at = self._clock.now()
            discount = uow.discounts.add(discount)
            record(
                uow,
                self._clock,
                actor,
                "discount.granted",
                entity="reservation",
                entity_id=reservation.id,
                discount_id=discount.id,
                amount=str(discount.amount(reservation.accommodation_total)),
            )
            return discount

    # ------------------------------------------------------------ tax exemptions (6.16)
    def exemptions(self, actor: Actor, reservation_id: int) -> list[TaxExemption]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.tax_exemptions.for_reservation(reservation_id)

    def exemptible_taxes(self, actor: Actor, reservation_id: int) -> list[TaxRule]:
        """The taxes this stay pays now, which a manager could exempt it from."""
        require_staff(actor)
        with self._uow() as uow:
            return applicable_taxes(uow, self._load(uow, reservation_id))

    def exempt_from_tax(self, actor: Actor, exemption: TaxExemption) -> TaxExemption:
        """A manager decides that this stay does not pay this tax, with a reason.

        Only while the bill is open: once the invoice is issued its taxes are
        final (corrections are refunds, BR22).
        """
        require_role(actor, Role.MANAGER)
        exemption.validate()
        with self._uow() as uow:
            reservation = self._load(uow, exemption.reservation_id)
            if reservation.status not in _OPEN_BILL:
                raise BusinessRuleViolation("tax.bill_closed")
            rule = uow.tax_rules.get(exemption.tax_rule_id)
            if rule is None or not rule.is_active:
                raise NotFoundError(entity="tax_rule", id=exemption.tax_rule_id)
            exemption.created_at = self._clock.now()
            exemption = uow.tax_exemptions.add(exemption, actor.user_id)
            record(
                uow,
                self._clock,
                actor,
                "tax.exempted",
                entity="reservation",
                entity_id=reservation.id,
                tax=rule.name,
                reason=exemption.reason,
            )
            return exemption

    def remove_exemption(self, actor: Actor, exemption_id: int) -> None:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            exemption = uow.tax_exemptions.get(exemption_id)
            if exemption is None:
                raise NotFoundError(entity="tax_exemption", id=exemption_id)
            reservation = self._load(uow, exemption.reservation_id)
            if reservation.status not in _OPEN_BILL:
                raise BusinessRuleViolation("tax.bill_closed")
            uow.tax_exemptions.delete(exemption_id)
            record(
                uow,
                self._clock,
                actor,
                "tax.exemption_removed",
                entity="reservation",
                entity_id=reservation.id,
                tax=exemption.tax_name,
            )

    def remove_discount(self, actor: Actor, discount_id: int) -> None:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            discount = uow.discounts.get(discount_id)
            if discount is None or not discount.is_active:
                raise NotFoundError(entity="discount", id=discount_id)
            reservation = self._load(uow, discount.reservation_id)
            if reservation.status not in _OPEN_BILL:
                raise BusinessRuleViolation("discount.bill_closed")
            discount.removed_at = self._clock.now()
            uow.discounts.remove(discount, actor.user_id)
            record(
                uow,
                self._clock,
                actor,
                "discount.removed",
                entity="reservation",
                entity_id=reservation.id,
                discount_id=discount.id,
            )

    # ------------------------------------------------------------ money
    def record_payment(
        self,
        actor: Actor,
        reservation_id: int,
        *,
        amount: Money,
        method: PaymentMethod,
        reference: str = "",
    ) -> Payment:
        """Story 4.6: a deposit before arrival (BR10), a payment afterwards."""
        require_staff(actor)
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            kind = payment_kind_for(reservation.status)
            return self._add_payment(uow, actor, reservation, kind, amount, method, reference)

    def refund(
        self,
        actor: Actor,
        reservation_id: int,
        *,
        amount: Money,
        method: PaymentMethod,
        reference: str = "",
    ) -> Payment:
        """Give back an overpayment (for example a deposit above a cancellation fee).

        Managers only (threat A6): money leaving the till needs a second person.
        """
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            reservation = self._load(uow, reservation_id)
            return self._add_payment(
                uow, actor, reservation, PaymentKind.REFUND, amount, method, reference
            )

    def _add_payment(
        self,
        uow: UnitOfWork,
        actor: Actor,
        reservation: Reservation,
        kind: PaymentKind,
        amount: Money,
        method: PaymentMethod,
        reference: str,
    ) -> Payment:
        reference = validate_reference(reference)
        check_payment(bill_for(uow, reservation), kind, amount)
        payment = uow.payments.add(
            Payment(
                id=None,
                reservation_id=reservation.id,
                kind=kind,
                method=method,
                amount=amount,
                paid_at=self._clock.now(),
                reference=reference,
                recorded_by=actor.user_id,
            )
        )
        record(
            uow,
            self._clock,
            actor,
            f"payment.{kind.value.lower()}",
            entity="reservation",
            entity_id=reservation.id,
            amount=str(amount),
            method=method.value,
        )
        return payment

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _load(uow: UnitOfWork, reservation_id: int) -> Reservation:
        reservation = uow.reservations.get(reservation_id)
        if reservation is None:
            raise NotFoundError(entity="reservation", id=reservation_id)
        return reservation

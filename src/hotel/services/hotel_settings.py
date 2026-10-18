"""Hotel settings and tax rules (story 4.8). Managers change; all staff read."""

from __future__ import annotations

from dataclasses import replace

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import BusinessRuleViolation, NotFoundError, StaleDataError
from hotel.domain.removal import RemovalAction, RemovalPlan, plan_removal
from hotel.domain.settings import HotelSettings
from hotel.domain.taxes import TaxRule
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role, require_staff

PREFIX = "hotel."


def load_settings(uow: UnitOfWork) -> HotelSettings:
    """Read the settings inside a transaction that is already open.

    Services that need a setting call this with their own Unit of Work: opening
    a second one would wait for the write lock the first one already holds.
    """
    return HotelSettings.from_strings(uow.settings.with_prefix(PREFIX))


class HotelSettingsService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    # ------------------------------------------------------------ settings
    def get(self, actor: Actor) -> HotelSettings:
        require_staff(actor)
        with self._uow() as uow:
            return load_settings(uow)

    def update(self, actor: Actor, new: HotelSettings) -> HotelSettings:
        require_role(actor, Role.MANAGER)
        new.validated()
        with self._uow() as uow:
            before = load_settings(uow).to_strings()
            after = new.to_strings()
            changed = {
                key: f"{before[key]} -> {after[key]}" for key in after if before[key] != after[key]
            }
            for key, value in after.items():
                uow.settings.set(PREFIX + key, value)
            if changed:
                record(uow, self._clock, actor, "settings.updated", entity="setting", **changed)
            return new

    # ------------------------------------------------------------ tax rules
    def tax_rules(self, actor: Actor, *, archived: bool = False) -> list[TaxRule]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.tax_rules.list(archived=archived)

    # ------------------------------------------------------------ delete or archive (6.17)
    def count_archived_taxes(self, actor: Actor) -> int:
        require_staff(actor)
        with self._uow() as uow:
            return uow.tax_rules.count_archived()

    def tax_removal_plan(self, actor: Actor, rule_id: int) -> RemovalPlan:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            self._load_rule(uow, rule_id)
            return plan_removal(uow.tax_rules.count_exemptions(rule_id))

    def remove_tax_rule(self, actor: Actor, rule_id: int) -> RemovalAction:
        """Delete or archive. Issued invoices keep their own copy of every tax line
        either way; only per-stay exemptions refer to the rule itself."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            rule = self._load_rule(uow, rule_id)
            plan = plan_removal(uow.tax_rules.count_exemptions(rule_id))
            if plan.action is RemovalAction.DELETE:
                uow.tax_rules.delete(rule_id)
            elif not rule.is_archived:
                uow.tax_rules.archive(rule_id, self._clock.now())
            action = "tax.deleted" if plan.action is RemovalAction.DELETE else "tax.archived"
            record(
                uow,
                self._clock,
                actor,
                action,
                entity="tax_rule",
                entity_id=rule_id,
                name=rule.name,
            )
            return plan.action

    def restore_tax_rule(self, actor: Actor, rule_id: int) -> TaxRule:
        """Back in the list, still inactive until a manager activates it."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            rule = self._load_rule(uow, rule_id)
            if rule.is_archived:
                uow.tax_rules.archive(rule_id, None)
                record(
                    uow, self._clock, actor, "tax.restored", entity="tax_rule", entity_id=rule_id
                )
            return uow.tax_rules.get(rule_id)

    @staticmethod
    def _load_rule(uow: UnitOfWork, rule_id: int) -> TaxRule:
        rule = uow.tax_rules.get(rule_id)
        if rule is None:
            raise NotFoundError(entity="tax_rule", id=rule_id)
        return rule

    def create_tax_rule(self, actor: Actor, rule: TaxRule) -> TaxRule:
        require_role(actor, Role.MANAGER)
        rule.validate()
        with self._uow() as uow:
            rule = uow.tax_rules.add(rule)
            record(
                uow,
                self._clock,
                actor,
                "tax.created",
                entity="tax_rule",
                entity_id=rule.id,
                name=rule.name,
                kind=rule.kind.value,
                payers=rule.payers.value,
            )
            return rule

    def update_tax_rule(self, actor: Actor, rule_id: int, rule: TaxRule) -> TaxRule:
        """Replace a rule's values. Issued invoices keep the old ones (they copy them)."""
        require_role(actor, Role.MANAGER)
        rule.validate()
        with self._uow() as uow:
            current = uow.tax_rules.get(rule_id)
            if current is None:
                raise NotFoundError(entity="tax_rule", id=rule_id)
            if current.version != rule.version:
                raise StaleDataError(entity="tax_rule", id=rule_id)
            if current.is_archived:
                raise BusinessRuleViolation("tax.archived")
            rule = replace(rule, id=rule_id)
            uow.tax_rules.update(rule)
            record(
                uow,
                self._clock,
                actor,
                "tax.updated",
                entity="tax_rule",
                entity_id=rule_id,
                name=rule.name,
                active=rule.is_active,
                payers=rule.payers.value,
            )
            return rule

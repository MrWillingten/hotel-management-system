"""Tax rules (decision G), written with the Strategy pattern.

Every rule answers the same question, "how much tax for this stay?", in its
own way: a percentage of a base amount (VAT) or a fixed amount per adult per
night (tourist tax). The bill only calls `amount()` and never needs to know
which kind of rule it is holding, so a new kind of tax is a new subclass,
not a new `if` in the billing code.

Prices are stored tax-exclusive. Real rates must be checked against current
Tunisian regulations before the system is used for real.
"""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from hotel.domain.errors import ValidationError
from hotel.domain.money import BASIS_POINTS_PER_UNIT, Money

MAX_PER_ADULT_NIGHT = Money.from_dinars(1_000)


class TaxKind(StrEnum):
    PERCENT = "PERCENT"
    PER_ADULT_NIGHT = "PER_ADULT_NIGHT"


class TaxPayers(StrEnum):
    """Who a rule taxes (story 6.16): a tourist tax, for example, may only
    concern guests who are not nationals of the hotel's country."""

    EVERYONE = "EVERYONE"
    FOREIGN = "FOREIGN"  # guests from another country than the hotel's
    NATIONALS = "NATIONALS"  # guests from the hotel's country


class TaxBase(StrEnum):
    """What a percentage tax is computed on."""

    ACCOMMODATION = "ACCOMMODATION"
    SERVICES = "SERVICES"


@dataclass(frozen=True, slots=True)
class TaxableStay:
    """The figures a tax rule may need, already after discounts."""

    accommodation: Money
    services: Money
    adult_nights: int  # sum over rooms of adults x nights charged


@dataclass(kw_only=True, slots=True)
class TaxRule(ABC):
    id: int | None = None
    name: str
    applies_to: TaxBase = TaxBase.ACCOMMODATION
    payers: TaxPayers = TaxPayers.EVERYONE
    is_active: bool = True
    version: int = 1
    archived_at: datetime | None = None  # story 6.17

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def concerns(self, national: bool) -> bool:
        """Does this rule tax a guest who is (or is not) a national of the hotel's country?"""
        if self.payers is TaxPayers.FOREIGN:
            return not national
        if self.payers is TaxPayers.NATIONALS:
            return national
        return True

    @property
    @abstractmethod
    def kind(self) -> TaxKind: ...

    @abstractmethod
    def amount(self, stay: TaxableStay) -> Money:
        """The tax for this stay, rounded half-up to the millime."""

    @abstractmethod
    def basis(self, stay: TaxableStay) -> tuple[int, Money]:
        """(quantity, unit) shown on the bill line, so the reader can check the sum."""

    @abstractmethod
    def validate(self) -> None:
        """Raise ValidationError if the rule's own values are out of range."""

    def _validate_name(self) -> None:
        name = " ".join(unicodedata.normalize("NFC", self.name).split())
        if not 1 <= len(name) <= 60:
            raise ValidationError("tax.name_invalid", fields={"name": "tax.name_invalid"})
        self.name = name


@dataclass(kw_only=True, slots=True)
class PercentTax(TaxRule):
    """A percentage of the accommodation or of the services (for example 7 % VAT)."""

    rate_bp: int  # basis points: 700 = 7.00 %

    @property
    def kind(self) -> TaxKind:
        return TaxKind.PERCENT

    def amount(self, stay: TaxableStay) -> Money:
        return self._base(stay).percent(self.rate_bp)

    def basis(self, stay: TaxableStay) -> tuple[int, Money]:
        return 1, self._base(stay)

    def _base(self, stay: TaxableStay) -> Money:
        return stay.accommodation if self.applies_to is TaxBase.ACCOMMODATION else stay.services

    def validate(self) -> None:
        self._validate_name()
        if not 1 <= self.rate_bp <= BASIS_POINTS_PER_UNIT:
            raise ValidationError("tax.rate_invalid", fields={"rate": "tax.rate_invalid"})


@dataclass(kw_only=True, slots=True)
class PerAdultNightTax(TaxRule):
    """A fixed amount per adult per night (for example a tourist tax)."""

    amount_per: Money

    @property
    def kind(self) -> TaxKind:
        return TaxKind.PER_ADULT_NIGHT

    def amount(self, stay: TaxableStay) -> Money:
        return self.amount_per.times(stay.adult_nights)

    def basis(self, stay: TaxableStay) -> tuple[int, Money]:
        return stay.adult_nights, self.amount_per

    def validate(self) -> None:
        self._validate_name()
        if self.applies_to is not TaxBase.ACCOMMODATION:
            raise ValidationError("tax.per_night_on_services")
        if self.amount_per.millimes <= 0 or self.amount_per > MAX_PER_ADULT_NIGHT:
            raise ValidationError("tax.amount_invalid", fields={"rate": "tax.amount_invalid"})


def is_national(nationality: str | None, id_doc_type: str, home_country: str) -> bool:
    """Is the guest a national of the hotel's country?

    The nationality decides. When it was not recorded, a Tunisian identity
    card (CIN) can only belong to a Tunisian, so it counts as national when
    the hotel is in Tunisia; anyone else counts as foreign.
    """
    if nationality:
        return nationality == home_country
    return id_doc_type == "CIN" and home_country == "TN"


def taxes_for_stay(
    rules: list[TaxRule], *, national: bool, exempt_rule_ids: set[int]
) -> list[TaxRule]:
    """The active rules this stay pays: those concerning the guest, minus exemptions."""
    return [
        rule
        for rule in rules
        if rule.is_active and rule.concerns(national) and rule.id not in exempt_rule_ids
    ]


MAX_EXEMPTION_REASON = 200


@dataclass(slots=True)
class TaxExemption:
    """A manager's decision that one stay does not pay one tax (story 6.16)."""

    id: int | None
    reservation_id: int
    tax_rule_id: int
    reason: str
    created_at: datetime | None = None
    created_by_name: str = ""  # filled when read, for display
    tax_name: str = ""

    def validate(self) -> None:
        reason = " ".join(unicodedata.normalize("NFC", self.reason).split())
        if not 1 <= len(reason) <= MAX_EXEMPTION_REASON:
            raise ValidationError(
                "reason.invalid",
                fields={"reason": "reason.invalid"},
                max_length=MAX_EXEMPTION_REASON,
            )
        self.reason = reason
